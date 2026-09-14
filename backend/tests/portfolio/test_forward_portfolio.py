from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.forward_portfolio import (
    ForwardEventType,
    ForwardOrderSide,
    ForwardOrderStatus,
    ForwardPortfolioStatus,
    ForwardPositionStatus,
)
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.database.models.research_portfolio import (
    PortfolioRecommendationStatus,
    PortfolioTickerPreference,
    ResearchPortfolio,
)
from alphapilot.portfolio.decisions import PortfolioDecision, PortfolioFinalAction
from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
    ForwardExecutionEligibilityReason,
    LossControlSource,
)
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.portfolio.sizing import PortfolioDecisionReason, PortfolioDecisionType
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.forward_portfolio import (
    ForwardDecisionBatch,
    ForwardMarketDataError,
    ForwardPortfolioService,
    MichoForwardDecisionProvider,
)
from alphapilot.strategy.signal import Signal

T = date(2026, 9, 7)
U = date(2026, 9, 8)
V = date(2026, 9, 9)
W = date(2026, 9, 10)
X = date(2026, 9, 11)


class ControlledDecisionProvider:
    def __init__(self, decisions_by_session: dict[date, tuple[PortfolioDecision, ...]]) -> None:
        self.decisions_by_session = decisions_by_session
        self.calls: list[date] = []

    async def decisions(self, *, trading_session: date, **kwargs) -> ForwardDecisionBatch:
        del kwargs
        self.calls.append(trading_session)
        return ForwardDecisionBatch(
            trading_session, self.decisions_by_session.get(trading_session, ())
        )


def decision(signal: Signal, *, ticker: str = "AAA") -> PortfolioDecision:
    buy = signal is Signal.BUY
    sell = signal is Signal.SELL
    return PortfolioDecision(
        ticker=ticker,
        signal=signal,
        decision=(
            PortfolioDecisionType.BUY
            if buy
            else PortfolioDecisionType.SELL
            if sell
            else PortfolioDecisionType.HOLD
        ),
        reason=(
            PortfolioDecisionReason.BUY_APPROVED
            if buy
            else PortfolioDecisionReason.SELL_APPROVED
            if sell
            else PortfolioDecisionReason.NO_ACTION
        ),
        ranking_score=Decimal("1.25") if buy else None,
        reference_price=Decimal("100") if not sell else Decimal("89"),
        atr=Decimal("2") if buy else None,
        stop_distance=None,
        risk_budget_dollars=Decimal("1000") if buy else Decimal("0"),
        target_allocation_dollars=Decimal("10000") if buy else Decimal("0"),
        target_weight_pct=Decimal("10") if buy else Decimal("0"),
        proposed_shares=100 if buy else 0,
        modeled_position_risk_dollars=Decimal("1000") if buy else Decimal("0"),
        sector="Industrials",
        sector_weight_before_pct=Decimal("0"),
        sector_weight_after_pct=Decimal("10") if buy else Decimal("0"),
        current_shares=99 if sell else 0,
        estimated_proceeds=Decimal("8811") if sell else None,
        execution_readiness=(
            ExecutionReadiness.ACTIONABLE if buy else ExecutionReadiness.RESEARCH_ONLY
        ),
        execution_readiness_reason=(
            ExecutionReadinessReason.LOSS_CONTROL_READY
            if buy
            else ExecutionReadinessReason.NOT_A_NEW_BUY
        ),
        loss_control_policy=("SMA150_COMPLETED_CLOSE_EXIT" if buy else "NONE"),
        loss_control_boundary_price=Decimal("90") if buy else None,
        loss_control_trigger=("COMPLETED_DAILY_CLOSE_BELOW" if buy else None),
        loss_control_active=buy,
        loss_control_source=(
            LossControlSource.APPROVED_SYSTEM_POLICY if buy else LossControlSource.NONE
        ),
        final_action=(
            PortfolioFinalAction.BUY
            if buy
            else PortfolioFinalAction.SELL
            if sell
            else PortfolioFinalAction.HOLD
        ),
        is_final_actionable=buy or sell,
        forward_execution_eligible=buy,
        forward_execution_reason=(
            ForwardExecutionEligibilityReason.MICHO_FORWARD_ELIGIBLE
            if buy
            else ForwardExecutionEligibilityReason.NOT_A_NEW_BUY
        ),
    )


async def seed_companies(session: AsyncSession) -> tuple[Company, Company]:
    spy = Company(ticker="SPY", name="SPY", exchange="NYSE", sector="ETF", is_active=True)
    stock = Company(ticker="AAA", name="AAA", exchange="NYSE", sector="Industrials", is_active=True)
    session.add_all([spy, stock])
    await session.commit()
    return spy, stock


async def add_session(
    session: AsyncSession,
    spy_id: UUID,
    stock_id: UUID,
    trading_session: date,
    *,
    stock_open: str,
    stock_close: str,
) -> None:
    session.add_all(
        [
            DailyCandle(
                company_id=spy_id,
                trading_day=trading_session,
                open=Decimal("500"),
                high=Decimal("505"),
                low=Decimal("495"),
                close=Decimal("502"),
                volume=1000,
            ),
            DailyCandle(
                company_id=stock_id,
                trading_day=trading_session,
                open=Decimal(stock_open),
                high=Decimal(stock_open) + Decimal("3"),
                low=Decimal(stock_open) - Decimal("3"),
                close=Decimal(stock_close),
                volume=1000,
            ),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_full_virtual_lifecycle_reconciles_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),), W: (decision(Signal.SELL),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    portfolio_id = portfolio.id

    assert await service.process_session(portfolio_id, T)
    orders = await service.orders(portfolio_id)
    assert len(orders) == 1
    assert orders[0].side == ForwardOrderSide.ENTRY.value
    assert orders[0].status == ForwardOrderStatus.PENDING.value
    assert await service.positions(portfolio_id) == []

    await add_session(db_session, spy.id, stock.id, U, stock_open="100", stock_close="102")
    assert await service.process_session(portfolio_id, U)
    positions = await service.positions(portfolio_id)
    assert len(positions) == 1
    assert positions[0].status == ForwardPositionStatus.OPEN.value
    assert positions[0].shares == 99
    assert positions[0].modeled_entry_price == Decimal("100.0500")
    current = await service.repo.get(portfolio_id)
    assert current is not None
    assert current.cash_balance == Decimal("90095.0500")

    await add_session(db_session, spy.id, stock.id, V, stock_open="104", stock_close="105")
    assert await service.process_session(portfolio_id, V)
    await add_session(db_session, spy.id, stock.id, W, stock_open="95", stock_close="89")
    assert await service.process_session(portfolio_id, W)
    orders = await service.orders(portfolio_id)
    exit_order = next(item for item in orders if item.side == ForwardOrderSide.EXIT.value)
    assert exit_order.status == ForwardOrderStatus.PENDING.value

    await add_session(db_session, spy.id, stock.id, X, stock_open="110", stock_close="111")
    assert await service.process_session(portfolio_id, X)
    assert not await service.process_session(portfolio_id, X)
    assert not await service.process_session(portfolio_id, X)
    trades = await service.trades(portfolio_id)
    assert len(trades) == 1
    assert trades[0].gross_pnl == Decimal("990.0000")
    assert trades[0].net_pnl == Decimal("979.6050")
    current = await service.repo.get(portfolio_id)
    assert current is not None
    assert current.cash_balance == Decimal("100979.6050")
    assert current.equity == Decimal("100979.6050")
    assert current.realized_pnl == Decimal("979.6050")
    analytics = await service.analytics(portfolio_id)
    assert analytics.completed_trades == 1
    assert analytics.open_trades == 0
    assert analytics.friction_dollars == Decimal("10.3950")
    assert analytics.strategy_exits == 1
    events = await service.events(portfolio_id)
    assert sum(item.event_type == ForwardEventType.POSITION_OPENED.value for item in events) == 1
    assert sum(item.event_type == ForwardEventType.POSITION_CLOSED.value for item in events) == 1
    assert sum(item.event_type == ForwardEventType.CYCLE_SKIPPED.value for item in events) == 1


@pytest.mark.asyncio
async def test_pause_blocks_new_entries_but_existing_exit_management_continues(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider(
        {
            T: (decision(Signal.BUY),),
            V: (decision(Signal.SELL),),
            W: (decision(Signal.BUY),),
        }
    )
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    portfolio_id = portfolio.id
    await service.process_session(portfolio_id, T)
    await add_session(db_session, spy.id, stock.id, U, stock_open="100", stock_close="102")
    await service.process_session(portfolio.id, U)
    paused = await service.pause(portfolio.id, expected_revision=2)
    assert paused.status == ForwardPortfolioStatus.PAUSED.value
    await add_session(db_session, spy.id, stock.id, V, stock_open="101", stock_close="89")
    await service.process_session(portfolio.id, V)
    exit_order = next(
        item
        for item in await service.orders(portfolio.id)
        if item.side == ForwardOrderSide.EXIT.value
    )
    assert exit_order.status == ForwardOrderStatus.PENDING.value
    await add_session(db_session, spy.id, stock.id, W, stock_open="95", stock_close="96")
    await service.process_session(portfolio.id, W)
    positions = await service.positions(portfolio.id)
    assert positions[0].status == ForwardPositionStatus.CLOSED.value
    assert not any(
        item.status == ForwardOrderStatus.PENDING.value
        and item.side == ForwardOrderSide.ENTRY.value
        for item in await service.orders(portfolio.id)
    )


@pytest.mark.asyncio
async def test_restart_catchup_processes_sessions_in_order(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    portfolio_id = portfolio.id
    await service.process_session(portfolio_id, T)
    for day in (U, V, W):
        await add_session(db_session, spy.id, stock.id, day, stock_open="100", stock_close="101")
    result = await service.run_pending(portfolio_id)
    assert result.processed_sessions == (U, V, W)
    assert provider.calls == [T, U, V, W]
    again = await service.run_pending(portfolio_id)
    assert again.processed_sessions == ()


@pytest.mark.asyncio
async def test_concurrent_same_session_has_one_economic_result(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    setup = ForwardPortfolioService(db_session, ControlledDecisionProvider({}))
    portfolio = await setup.initialize(initial_cash=Decimal("100000"), forward_start_session=T)

    session_factory = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as first_session, session_factory() as second_session:
        first = ForwardPortfolioService(first_session, ControlledDecisionProvider({}))
        second = ForwardPortfolioService(second_session, ControlledDecisionProvider({}))
        outcomes = await asyncio.gather(
            first.process_session(portfolio.id, T),
            second.process_session(portfolio.id, T),
        )
    assert sorted(outcomes) == [False, True]
    events = await setup.events(portfolio.id)
    assert sum(item.event_type == ForwardEventType.CYCLE_COMPLETED.value for item in events) == 1


@pytest.mark.asyncio
async def test_missing_next_open_rolls_back_and_retries_same_session(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    spy_id, stock_id = spy.id, stock.id
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    portfolio_id = portfolio.id
    await service.process_session(portfolio_id, T)

    db_session.add(
        DailyCandle(
            company_id=spy_id,
            trading_day=U,
            open=Decimal("500"),
            high=Decimal("505"),
            low=Decimal("495"),
            close=Decimal("502"),
            volume=1000,
        )
    )
    await db_session.commit()
    with pytest.raises(ForwardMarketDataError, match="ENTRY_OPEN_MISSING"):
        await service.process_session(portfolio_id, U)
    current = await service.repo.get(portfolio_id)
    assert current is not None
    assert current.last_processed_session == T
    assert current.cash_balance == Decimal("100000.0000")
    events = await service.events(portfolio_id)
    assert sum(item.event_type == ForwardEventType.DATA_UNAVAILABLE.value for item in events) == 1
    assert sum(item.event_type == ForwardEventType.CYCLE_FAILED.value for item in events) == 1

    db_session.add(
        DailyCandle(
            company_id=stock_id,
            trading_day=U,
            open=Decimal("100"),
            high=Decimal("103"),
            low=Decimal("97"),
            close=Decimal("102"),
            volume=1000,
        )
    )
    await db_session.commit()
    assert await service.process_session(portfolio_id, U)
    assert len(await service.positions(portfolio_id)) == 1
    assert not await service.process_session(portfolio_id, U)


@pytest.mark.asyncio
async def test_duplicate_buy_while_open_does_not_pyramid_and_gap_caps_shares(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),), U: (decision(Signal.BUY),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    portfolio_id = portfolio.id
    await service.process_session(portfolio_id, T)
    await add_session(db_session, spy.id, stock.id, U, stock_open="125", stock_close="126")
    await service.process_session(portfolio_id, U)

    positions = await service.positions(portfolio_id)
    entries = [item for item in await service.orders(portfolio_id) if item.side == "ENTRY"]
    assert len(positions) == 1
    assert positions[0].shares == 79
    assert len(entries) == 1
    current = await service.repo.get(portfolio_id)
    assert current is not None
    assert current.cash_balance >= 0
    assert any(
        item.event_type == ForwardEventType.SIGNAL_SKIPPED.value
        and item.reason_code == "ALREADY_HELD"
        for item in await service.events(portfolio_id)
    )


@pytest.mark.asyncio
async def test_micho_gap_below_sma_is_not_an_intraday_stop(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),), U: (decision(Signal.SELL),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    portfolio_id = portfolio.id
    await service.process_session(portfolio_id, T)

    await add_session(db_session, spy.id, stock.id, U, stock_open="80", stock_close="79")
    await service.process_session(portfolio_id, U)
    positions = await service.positions(portfolio_id)
    assert len(positions) == 1
    assert positions[0].status == ForwardPositionStatus.OPEN.value
    assert positions[0].shares == 100
    assert positions[0].risk_per_share == Decimal("10.0000")
    assert positions[0].loss_control_boundary == Decimal("90.0000")
    assert any(
        item.side == ForwardOrderSide.EXIT.value and item.status == ForwardOrderStatus.PENDING.value
        for item in await service.orders(portfolio_id)
    )
    assert not any(
        item.event_type == ForwardEventType.STOP_TRIGGERED.value
        for item in await service.events(portfolio_id)
    )

    await add_session(db_session, spy.id, stock.id, V, stock_open="78", stock_close="78")
    await service.process_session(portfolio_id, V)
    trades = await service.trades(portfolio_id)
    assert len(trades) == 1
    assert trades[0].exit_reason == "MICHO_CLOSE_BELOW_SMA150"
    assert trades[0].raw_exit_price == Decimal("78.0000")
    assert trades[0].modeled_exit_price == Decimal("77.9610")


@pytest.mark.asyncio
async def test_max_ten_slots_prevents_eleventh_pending_entry(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    tickers = ["AAA", *(f"T{number:02d}" for number in range(1, 11))]
    extra = [
        Company(
            ticker=ticker,
            name=ticker,
            exchange="NYSE",
            sector="Industrials",
            is_active=True,
        )
        for ticker in tickers[1:]
    ]
    db_session.add_all(extra)
    await db_session.commit()
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    for company in extra:
        db_session.add(
            DailyCandle(
                company_id=company.id,
                trading_day=T,
                open=Decimal("98"),
                high=Decimal("101"),
                low=Decimal("95"),
                close=Decimal("100"),
                volume=1000,
            )
        )
    await db_session.commit()
    provider = ControlledDecisionProvider(
        {T: tuple(decision(Signal.BUY, ticker=ticker) for ticker in tickers)}
    )
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await service.process_session(portfolio.id, T)
    pending = [item for item in await service.orders(portfolio.id) if item.status == "PENDING"]
    assert len(pending) == 10
    assert {item.ticker for item in pending} == set(tickers[:10])
    events = await service.events(portfolio.id)
    assert any(
        item.event_type == ForwardEventType.SIGNAL_SKIPPED.value
        and item.ticker == tickers[10]
        and item.reason_code == "MAX_POSITIONS"
        for item in events
    )


@pytest.mark.asyncio
async def test_default_research_preference_excludes_new_forward_entry_without_mutation(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    research = ResearchPortfolio(
        stable_key="default", name="Research Portfolio", cash_balance=Decimal("12345")
    )
    db_session.add(research)
    await db_session.flush()
    db_session.add(
        PortfolioTickerPreference(
            portfolio_id=research.id,
            company_id=stock.id,
            ticker="AAA",
            recommendation_status=PortfolioRecommendationStatus.USER_EXCLUDED.value,
        )
    )
    await db_session.commit()
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await service.process_session(portfolio.id, T)
    assert await service.orders(portfolio.id) == []
    assert await service.positions(portfolio.id) == []
    assert await service.repo.excluded_tickers() == frozenset({"AAA"})
    await db_session.refresh(research)
    assert research.cash_balance == Decimal("12345.0000")
    assert any(
        item.event_type == ForwardEventType.SIGNAL_SKIPPED.value
        and item.reason_code == "USER_EXCLUDED"
        for item in await service.events(portfolio.id)
    )


@pytest.mark.asyncio
async def test_insufficient_cash_at_fill_cancels_without_debit(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("1"), forward_start_session=T)
    await service.process_session(portfolio.id, T)
    await add_session(db_session, spy.id, stock.id, U, stock_open="100", stock_close="101")
    await service.process_session(portfolio.id, U)
    orders = await service.orders(portfolio.id)
    assert len(orders) == 1
    assert orders[0].status == ForwardOrderStatus.CANCELLED.value
    assert orders[0].reason_code == "INSUFFICIENT_CASH_AT_FILL"
    assert await service.positions(portfolio.id) == []
    current = await service.repo.get(portfolio.id)
    assert current is not None
    assert current.cash_balance == Decimal("1.0000")
    assert current.equity == Decimal("1.0000")


@pytest.mark.asyncio
async def test_real_micho_orchestrator_creates_only_final_approved_pending_entry(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    db_session.add(IndexConstituent(index_symbol="^GSPC", ticker="AAA", is_active=True))
    days: list[date] = []
    candidate_day = date(2025, 1, 2)
    while len(days) < 156:
        if candidate_day.weekday() < 5:
            days.append(candidate_day)
        candidate_day += timedelta(days=1)
    for index, day in enumerate(days):
        stock_close = Decimal("103") if index == len(days) - 1 else Decimal("100")
        db_session.add_all(
            [
                DailyCandle(
                    company_id=spy.id,
                    trading_day=day,
                    open=Decimal("500"),
                    high=Decimal("501"),
                    low=Decimal("499"),
                    close=Decimal("500"),
                    volume=1000,
                ),
                DailyCandle(
                    company_id=stock.id,
                    trading_day=day,
                    open=Decimal("100"),
                    high=Decimal("105"),
                    low=Decimal("99"),
                    close=stock_close,
                    volume=1000,
                ),
            ]
        )
    await db_session.commit()
    signal_day = days[-1]
    orchestrator = PortfolioDecisionOrchestrator(
        CompanyService(CompanyRepository(db_session)),
        DailyCandleService(DailyCandleRepository(db_session)),
        IndexConstituentRepository(db_session),
    )
    service = ForwardPortfolioService(db_session, MichoForwardDecisionProvider(orchestrator))
    portfolio = await service.initialize(
        initial_cash=Decimal("100000"), forward_start_session=signal_day
    )
    await service.process_session(portfolio.id, signal_day)
    orders = await service.orders(portfolio.id)
    assert len(orders) == 1
    assert orders[0].ticker == "AAA"
    assert orders[0].status == ForwardOrderStatus.PENDING.value
    assert orders[0].loss_control_policy == "SMA150_COMPLETED_CLOSE_EXIT"
    assert orders[0].loss_control_trigger == "COMPLETED_DAILY_CLOSE_BELOW"
    assert orders[0].loss_control_boundary is not None
    assert orders[0].evidence["final_action"] == "BUY"
    assert orders[0].evidence["is_final_actionable"] is True
    assert await service.positions(portfolio.id) == []


@pytest.mark.asyncio
async def test_forward_start_never_replays_earlier_economic_signal(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    await add_session(db_session, spy.id, stock.id, U, stock_open="100", stock_close="101")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("100000"), forward_start_session=U)
    result = await service.run_pending(portfolio.id)
    assert result.processed_sessions == (U,)
    assert provider.calls == [U]
    assert await service.orders(portfolio.id) == []
    assert await service.positions(portfolio.id) == []
    current = await service.repo.get(portfolio.id)
    assert current is not None
    assert current.cash_balance == Decimal("100000.0000")


@pytest.mark.asyncio
async def test_opening_exit_proceeds_can_fund_opening_entry(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    other = Company(ticker="BBB", name="BBB", exchange="NYSE", sector="Industrials", is_active=True)
    db_session.add(other)
    await db_session.commit()
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    db_session.add(
        DailyCandle(
            company_id=other.id,
            trading_day=T,
            open=Decimal("98"),
            high=Decimal("101"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=1000,
        )
    )
    await db_session.commit()
    provider = ControlledDecisionProvider(
        {
            T: (decision(Signal.BUY),),
            V: (decision(Signal.SELL), decision(Signal.BUY, ticker="BBB")),
        }
    )
    service = ForwardPortfolioService(db_session, provider)
    portfolio = await service.initialize(initial_cash=Decimal("10000"), forward_start_session=T)
    portfolio_id = portfolio.id
    await service.process_session(portfolio_id, T)
    await add_session(db_session, spy.id, stock.id, U, stock_open="100", stock_close="102")
    db_session.add(
        DailyCandle(
            company_id=other.id,
            trading_day=U,
            open=Decimal("100"),
            high=Decimal("103"),
            low=Decimal("97"),
            close=Decimal("102"),
            volume=1000,
        )
    )
    await db_session.commit()
    await service.process_session(portfolio_id, U)
    await add_session(db_session, spy.id, stock.id, V, stock_open="103", stock_close="89")
    db_session.add(
        DailyCandle(
            company_id=other.id,
            trading_day=V,
            open=Decimal("100"),
            high=Decimal("103"),
            low=Decimal("97"),
            close=Decimal("100"),
            volume=1000,
        )
    )
    await db_session.commit()
    await service.process_session(portfolio_id, V)
    await add_session(db_session, spy.id, stock.id, W, stock_open="110", stock_close="111")
    db_session.add(
        DailyCandle(
            company_id=other.id,
            trading_day=W,
            open=Decimal("100"),
            high=Decimal("103"),
            low=Decimal("97"),
            close=Decimal("101"),
            volume=1000,
        )
    )
    await db_session.commit()
    await service.process_session(portfolio_id, W)

    open_positions = [
        item for item in await service.positions(portfolio_id) if item.status == "OPEN"
    ]
    assert [(item.ticker, item.shares) for item in open_positions] == [("BBB", 99)]
    assert len(await service.trades(portfolio_id)) == 1
    current = await service.repo.get(portfolio_id)
    assert current is not None
    assert current.cash_balance == Decimal("1074.6550")
