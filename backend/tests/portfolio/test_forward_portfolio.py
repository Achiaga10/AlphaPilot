from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.external_execution import (
    ExternalExecutionCase,
    ExternalExecutionFill,
)
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
from alphapilot.schemas.external_execution import ExternalFillRequest, ExternalSkipReason
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.external_execution import (
    ExternalExecutionConflictError,
    ExternalExecutionService,
)
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
    external_actions = await ExternalExecutionService(db_session).list_actions(portfolio.id)
    assert [(item.side, item.ticker) for item in external_actions] == [
        ("SELL", "AAA"),
        ("BUY", "AAA"),
    ]
    assert external_actions[0].source_signal_session == V
    assert external_actions[0].status == "AWAITING_RECORD"


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


def external_fill(
    key: str,
    quantity: int,
    price: str,
    *,
    side: str = "BUY",
    fee: str | None = "0",
    mark_complete: bool = True,
    day: date = U,
) -> ExternalFillRequest:
    return ExternalFillRequest(
        request_key=key,
        side=side,
        quantity=quantity,
        price=Decimal(price),
        executed_at=datetime(
            day.year, day.month, day.day, 9, 35, tzinfo=ZoneInfo("America/New_York")
        ),
        fee=Decimal(fee) if fee is not None else None,
        mark_complete=mark_complete,
    )


@pytest.mark.asyncio
async def test_external_entry_partial_replay_correction_and_virtual_isolation(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    forward = ForwardPortfolioService(
        db_session, ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    )
    portfolio = await forward.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await forward.process_session(portfolio.id, T)
    external = ExternalExecutionService(db_session)
    actions = await external.list_actions(portfolio.id)
    assert len(actions) == 1
    action = actions[0]
    assert (action.ticker, action.side, action.planned_shares) == ("AAA", "BUY", 100)
    assert action.status == "AWAITING_ACTION"
    assert action.source_signal_session == T
    assert action.provenance == "MANUAL_USER_RECORDED"
    assert action.weighted_fill_price is None
    portfolio_id = portfolio.id
    action_id = action.id
    spy_id, stock_id = spy.id, stock.id

    first = external_fill("partial-0001", 40, "100", mark_complete=False)
    partial = await external.record_fill(portfolio.id, action.id, first)
    assert partial.status == "PARTIALLY_RECORDED"
    assert partial.recorded_shares == 40
    replay = await external.record_fill(portfolio.id, action.id, first)
    assert len(replay.fills) == 1
    with pytest.raises(ExternalExecutionConflictError):
        await external.record_fill(
            portfolio_id, action_id, external_fill("partial-0001", 41, "100")
        )
    await db_session.rollback()

    second = await external.record_fill(
        portfolio_id,
        action_id,
        external_fill("partial-0002", 30, "100.10", fee="0.50", mark_complete=False),
    )
    assert second.recorded_shares == 70
    completed = await external.record_fill(
        portfolio_id, action_id, external_fill("partial-0003", 29, "100.20", fee="0.25")
    )
    assert completed.status == "RECORDED"
    assert completed.recorded_shares == 99
    assert completed.weighted_fill_price == Decimal("100.08888889")
    assert completed.recorded_fees == Decimal("0.7500")
    assert completed.share_variance_vs_planned == -1
    assert completed.virtual_modeled_fill_price is None

    second_fill_id = completed.fills[1].id
    corrected = await external.void_fill(
        portfolio_id,
        second_fill_id,
        reason="Correcting typed price",
        request_key="void-partial-0002",
    )
    assert corrected.recorded_shares == 69
    assert corrected.fills[1].voided_at is not None
    assert any(event.event_type == "EXTERNAL_FILL_VOIDED" for event in corrected.events)
    corrected = await external.record_fill(
        portfolio_id, action_id, external_fill("partial-0004", 30, "100.15", fee="0.50")
    )
    assert corrected.recorded_shares == 99
    assert len(corrected.fills) == 4
    assert corrected.weighted_fill_price == Decimal("100.10404040")
    current = await forward.repo.get(portfolio_id)
    assert current is not None and current.cash_balance == Decimal("100000.0000")

    await add_session(db_session, spy_id, stock_id, U, stock_open="100", stock_close="102")
    await forward.process_session(portfolio_id, U)
    after_virtual = await external.get_action(portfolio_id, action_id)
    assert after_virtual.virtual_filled_shares == 99
    assert after_virtual.reconciliation_status == "PRICE_DIVERGENCE"
    assert after_virtual.price_difference_bps is not None
    assert after_virtual.price_difference_bps > 0
    current = await forward.repo.get(portfolio_id)
    assert current is not None and current.cash_balance == Decimal("90095.0500")


@pytest.mark.asyncio
async def test_external_skipped_entry_does_not_block_virtual_exit(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    provider = ControlledDecisionProvider({T: (decision(Signal.BUY),), W: (decision(Signal.SELL),)})
    forward = ForwardPortfolioService(db_session, provider)
    portfolio = await forward.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await forward.process_session(portfolio.id, T)
    external = ExternalExecutionService(db_session)
    entry = (await external.list_actions(portfolio.id))[0]
    skipped = await external.skip(portfolio.id, entry.id, ExternalSkipReason.MISSED_ENTRY)
    assert skipped.status == "SKIPPED"
    assert skipped.reconciliation_status == "SKIPPED"
    portfolio_id = portfolio.id
    spy_id, stock_id = spy.id, stock.id
    with pytest.raises(ExternalExecutionConflictError):
        await external.record_fill(portfolio_id, entry.id, external_fill("skipped-fill", 99, "100"))
    await db_session.rollback()
    await add_session(db_session, spy_id, stock_id, U, stock_open="100", stock_close="102")
    await forward.process_session(portfolio_id, U)
    await add_session(db_session, spy_id, stock_id, V, stock_open="104", stock_close="105")
    await forward.process_session(portfolio_id, V)
    await add_session(db_session, spy_id, stock_id, W, stock_open="95", stock_close="89")
    await forward.process_session(portfolio_id, W)
    exit_action = next(
        item for item in await external.list_actions(portfolio_id) if item.side == "SELL"
    )
    assert exit_action.status == "AWAITING_ACTION"
    assert exit_action.source_signal_session == W
    assert exit_action.planned_shares == 99
    await add_session(db_session, spy_id, stock_id, X, stock_open="110", stock_close="111")
    await forward.process_session(portfolio_id, X)
    comparison = (await external.trade_comparisons(portfolio_id))[0]
    assert comparison.completeness == "SKIPPED"
    assert comparison.recorded_execution_pnl is None
    assert comparison.virtual_net_pnl == Decimal("979.6050")
    current = await forward.repo.get(portfolio_id)
    assert current is not None and current.cash_balance == Decimal("100979.6050")


@pytest.mark.asyncio
async def test_external_recorded_full_trade_reconciles_exact_decimal(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    forward = ForwardPortfolioService(
        db_session,
        ControlledDecisionProvider({T: (decision(Signal.BUY),), W: (decision(Signal.SELL),)}),
    )
    portfolio = await forward.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await forward.process_session(portfolio.id, T)
    external = ExternalExecutionService(db_session)
    entry = (await external.list_actions(portfolio.id))[0]
    await external.record_fill(
        portfolio.id, entry.id, external_fill("entry-fill-95", 95, "100.17", fee="1")
    )
    await add_session(db_session, spy.id, stock.id, U, stock_open="100", stock_close="102")
    await forward.process_session(portfolio.id, U)
    await add_session(db_session, spy.id, stock.id, V, stock_open="104", stock_close="105")
    await forward.process_session(portfolio.id, V)
    await add_session(db_session, spy.id, stock.id, W, stock_open="95", stock_close="89")
    await forward.process_session(portfolio.id, W)
    exit_action = next(
        item for item in await external.list_actions(portfolio.id) if item.side == "SELL"
    )
    assert exit_action.status == "AWAITING_ACTION"
    await add_session(db_session, spy.id, stock.id, X, stock_open="110", stock_close="111")
    await forward.process_session(portfolio.id, X)
    missing_exit = (await external.trade_comparisons(portfolio.id))[0]
    assert missing_exit.completeness == "MISSING_EXIT"
    assert missing_exit.recorded_execution_pnl is None
    await external.record_fill(
        portfolio.id,
        exit_action.id,
        external_fill("exit-fill-95", 95, "109.90", side="SELL", fee="1", day=X),
    )
    comparison = (await external.trade_comparisons(portfolio.id))[0]
    assert comparison.completeness == "COMPLETE"
    assert comparison.virtual_shares == 99
    assert comparison.recorded_entry_shares == 95
    assert comparison.recorded_exit_shares == 95
    assert comparison.recorded_gross_pnl == Decimal("924.3500")
    assert comparison.recorded_execution_pnl == Decimal("922.3500")
    assert comparison.pnl_difference == Decimal("-57.2550")
    analytics = await external.analytics(portfolio.id)
    assert analytics.completed_fully_reconciled_trades == 1
    assert analytics.matched_virtual_pnl == Decimal("979.6050")
    assert analytics.matched_recorded_execution_pnl == Decimal("922.3500")


@pytest.mark.asyncio
async def test_external_action_virtual_cancel_and_concurrent_request_replay(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    forward = ForwardPortfolioService(
        db_session, ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    )
    portfolio = await forward.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await forward.process_session(portfolio.id, T)
    external = ExternalExecutionService(db_session)
    case_id = (await external.list_actions(portfolio.id))[0].id
    session_factory = async_sessionmaker(
        bind=db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as first_session, session_factory() as second_session:
        first = ExternalExecutionService(first_session)
        second = ExternalExecutionService(second_session)
        outcomes = await asyncio.gather(
            first.record_fill(
                portfolio.id, case_id, external_fill("concurrent-fill", 95, "100.20")
            ),
            second.record_fill(
                portfolio.id, case_id, external_fill("concurrent-fill", 95, "100.20")
            ),
        )
    assert all(item.recorded_shares == 95 for item in outcomes)
    assert len((await external.get_action(portfolio.id, case_id)).fills) == 1
    current = await forward.repo.get(portfolio.id)
    assert current is not None
    await forward.pause(portfolio.id, expected_revision=current.revision)
    cancelled = await external.get_action(portfolio.id, case_id)
    assert cancelled.virtual_order_status == "CANCELLED"
    assert cancelled.reconciliation_status == "EXECUTED_AFTER_VIRTUAL_CANCEL"
    assert cancelled.recorded_shares == 95


@pytest.mark.asyncio
async def test_external_execution_api_validation_replay_and_observational_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    forward = ForwardPortfolioService(
        db_session, ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    )
    portfolio = await forward.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await forward.process_session(portfolio.id, T)
    root = f"/api/v1/forward-portfolio/{portfolio.id}"
    actions = await client.get(f"{root}/external-actions")
    assert actions.status_code == 200
    case_id = actions.json()[0]["id"]
    assert actions.json()[0]["status"] == "AWAITING_ACTION"
    single = await client.get(f"{root}/external-actions/{case_id}")
    assert single.status_code == 200
    assert single.json()["forward_order_id"] == actions.json()[0]["forward_order_id"]

    fill_url = f"{root}/external-actions/{case_id}/fills"
    payload = external_fill("api-fill-0001", 95, "100.17", fee=None).model_dump(mode="json")
    for invalid in (
        {**payload, "quantity": 0},
        {**payload, "price": "0"},
        {**payload, "price": "NaN"},
        {**payload, "price": "Infinity"},
        {**payload, "fee": "-1"},
        {**payload, "executed_at": "not-a-date"},
    ):
        assert (await client.post(fill_url, json=invalid)).status_code == 422
    wrong_side = await client.post(fill_url, json={**payload, "side": "SELL"})
    assert wrong_side.status_code == 422
    recorded = await client.post(fill_url, json=payload)
    assert recorded.status_code == 200
    assert recorded.json()["recorded_shares"] == 95
    assert recorded.json()["status"] == "RECORDED"
    assert recorded.json()["recorded_fees"] is None
    replay = await client.post(fill_url, json=payload)
    assert replay.status_code == 200
    assert len(replay.json()["fills"]) == 1
    conflict = await client.post(fill_url, json={**payload, "quantity": 96})
    assert conflict.status_code == 409

    skip_url = f"{root}/external-actions/{case_id}/skip"
    assert (
        await client.post(skip_url, json={"confirmed": False, "reason": "USER_SKIPPED"})
    ).status_code == 422
    assert (
        await client.post(skip_url, json={"confirmed": True, "reason": "USER_SKIPPED"})
    ).status_code == 409
    fill_id = recorded.json()["fills"][0]["id"]
    void_url = f"{root}/external-fills/{fill_id}/void"
    void_payload = {
        "confirmed": True,
        "request_key": "api-void-0001",
        "reason": "Correct user-entered fill",
    }
    assert (
        await client.post(void_url, json={**void_payload, "confirmed": False})
    ).status_code == 422
    voided = await client.post(void_url, json=void_payload)
    assert voided.status_code == 200
    assert voided.json()["fills"][0]["void_reason"] == "Correct user-entered fill"
    assert (await client.post(void_url, json=void_payload)).status_code == 200
    assert (await client.get(f"{root}/reconciliation")).json() == []
    analytics = await client.get(f"{root}/execution-analytics")
    assert analytics.status_code == 200
    assert analytics.json()["expected_actions"] == 1
    current = await forward.repo.get(portfolio.id)
    assert current is not None and current.cash_balance == Decimal("100000.0000")


@pytest.mark.asyncio
async def test_external_execution_database_constraints_are_durable(
    db_session: AsyncSession,
) -> None:
    spy, stock = await seed_companies(db_session)
    await add_session(db_session, spy.id, stock.id, T, stock_open="98", stock_close="100")
    forward = ForwardPortfolioService(
        db_session, ControlledDecisionProvider({T: (decision(Signal.BUY),)})
    )
    portfolio = await forward.initialize(initial_cash=Decimal("100000"), forward_start_session=T)
    await forward.process_session(portfolio.id, T)
    case = (await ExternalExecutionService(db_session).list_actions(portfolio.id))[0]
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                ExternalExecutionCase(
                    portfolio_id=portfolio.id,
                    forward_order_id=case.forward_order_id,
                    broker="ALPACA",
                    provenance="MANUAL_USER_RECORDED",
                )
            )
            await db_session.flush()
    for key, quantity, price, fee in (
        ("bad-quantity", 0, "100", "0"),
        ("bad-price", 1, "0", "0"),
        ("bad-fee", 1, "100", "-1"),
    ):
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                db_session.add(
                    ExternalExecutionFill(
                        case_id=case.id,
                        request_key=key,
                        side="BUY",
                        quantity=quantity,
                        price=Decimal(price),
                        executed_at=datetime.now(UTC),
                        fee=Decimal(fee),
                        mark_complete=True,
                        source="MANUAL_USER_RECORDED",
                        created_at=datetime.now(UTC),
                    )
                )
                await db_session.flush()
