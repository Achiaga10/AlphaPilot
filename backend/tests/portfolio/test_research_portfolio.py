from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.research_portfolio import (
    ResearchPosition,
    ResearchPositionProvenance,
    ResearchPositionStatus,
    ResearchTradeEvent,
    ResearchTradeEventType,
)
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.services.research_portfolio import (
    ImportedPosition,
    PortfolioValuationStatus,
    ResearchPortfolioService,
    StalePortfolioRevisionError,
)


async def _company(session, ticker: str = "AAA") -> Company:
    company = Company(ticker=ticker, name=ticker, exchange="NYSE", sector="Technology")
    session.add(company)
    await session.commit()
    return company


async def _candle(session, company: Company, day: date, close: str) -> None:
    value = Decimal(close)
    session.add(
        DailyCandle(
            company_id=company.id,
            trading_day=day,
            open=value,
            high=value,
            low=value,
            close=value,
            volume=100,
        )
    )
    await session.commit()


async def _buy(service: ResearchPortfolioService, portfolio_id, revision: int = 0) -> None:
    await service.buy(
        portfolio_id=portfolio_id,
        expected_revision=revision,
        ticker="AAA",
        quantity=10,
        execution_price=Decimal("100"),
        trading_day=date(2025, 1, 2),
        strategy="ema20-pullback",
        profile_id="ema20-pullback-v1",
        profile_version=1,
        profile_snapshot={"profile_id": "ema20-pullback-v1", "version": 1},
        selection_policy="relative-strength-20",
        decision="BUY",
        reason="BUY_APPROVED",
        modeled_risk_dollars=Decimal("50"),
        action_id="buy-aaa",
    )


@pytest.mark.asyncio
async def test_buy_persists_cash_position_profile_and_event(db_session) -> None:
    await _company(db_session)
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("10000"))
    await _buy(service, portfolio.id)

    fresh_service = ResearchPortfolioService(db_session)
    current = await fresh_service.current()
    assert current is not None
    assert current.cash_balance == Decimal("9000")
    assert current.revision == 1
    positions = await fresh_service.portfolios.list_open_positions(current.id)
    assert len(positions) == 1
    position = positions[0]
    assert position.ticker_at_entry == "AAA"
    assert position.quantity == 10
    assert position.average_entry_cost == Decimal("100")
    assert position.cost_basis == Decimal("1000")
    assert position.strategy_profile_id == "ema20-pullback-v1"
    assert position.strategy_profile_version == 1
    assert position.strategy_profile_snapshot == {
        "profile_id": "ema20-pullback-v1",
        "version": 1,
    }
    events = await fresh_service.events(current.id)
    assert [(item.event_type, item.quantity) for item in events] == [("OPEN", 10)]


@pytest.mark.asyncio
async def test_legacy_import_is_one_time_and_does_not_fabricate_provenance(db_session) -> None:
    await _company(db_session)
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(
        starting_cash=Decimal("5000"),
        imported_positions=(ImportedPosition("AAA", 2, Decimal("90"), Decimal("180")),),
    )
    again = await service.initialize(
        starting_cash=Decimal("999999"),
        imported_positions=(ImportedPosition("AAA", 5, Decimal("1")),),
    )
    assert again.id == portfolio.id
    assert again.cash_balance == Decimal("5000")
    positions = await service.portfolios.list_open_positions(portfolio.id)
    assert len(positions) == 1
    assert positions[0].provenance_status == ResearchPositionProvenance.LEGACY_IMPORTED
    assert positions[0].strategy is None
    assert positions[0].strategy_profile_id is None
    assert await service.events(portfolio.id) == []


@pytest.mark.asyncio
async def test_primary_acceptance_marks_to_market_without_rewriting_entry(db_session) -> None:
    company = await _company(db_session)
    await _candle(db_session, company, date(2025, 1, 2), "100")
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("10000"))
    await _buy(service, portfolio.id)

    first = await service.value(portfolio.id)
    assert first.cash == Decimal("9000")
    assert first.total_equity == Decimal("10000")
    assert first.positions[0].market_value == Decimal("1000")
    assert first.positions[0].unrealized_pnl == Decimal("0")

    await _candle(db_session, company, date(2025, 1, 3), "110")
    second = await service.value(portfolio.id)
    assert second.total_equity == Decimal("10100")
    assert second.positions[0].market_value == Decimal("1100")
    assert second.positions[0].unrealized_pnl == Decimal("100")
    assert second.positions[0].unrealized_pnl_pct == Decimal("10.0")
    stored = (
        await db_session.execute(
            select(ResearchPosition).where(ResearchPosition.id == second.positions[0].position_id)
        )
    ).scalar_one()
    assert stored.average_entry_cost == Decimal("100")
    assert stored.cost_basis == Decimal("1000")
    assert stored.entry_price == Decimal("100")


@pytest.mark.asyncio
async def test_incomplete_session_is_ignored_for_valuation(db_session) -> None:
    company = await _company(db_session)
    await _candle(db_session, company, date(2025, 1, 2), "100")
    await _candle(db_session, company, date(2025, 1, 3), "999")
    policy = CompletedDailySessionPolicy(
        now_provider=lambda: datetime(2025, 1, 3, 15, 0, tzinfo=UTC)
    )
    service = ResearchPortfolioService(
        db_session,
        candle_repository=DailyCandleRepository(db_session, policy),
    )
    portfolio = await service.initialize(
        starting_cash=Decimal("9000"),
        imported_positions=(ImportedPosition("AAA", 10, Decimal("100")),),
    )
    valuation = await service.value(portfolio.id)
    assert valuation.positions[0].latest_completed_trading_day == date(2025, 1, 2)
    assert valuation.positions[0].latest_completed_close == Decimal("100")


@pytest.mark.asyncio
async def test_missing_price_is_explicit_and_totals_are_unavailable(db_session) -> None:
    await _company(db_session)
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(
        starting_cash=Decimal("9000"),
        imported_positions=(ImportedPosition("AAA", 10, Decimal("100")),),
    )
    valuation = await service.value(portfolio.id)
    assert valuation.valuation_status == PortfolioValuationStatus.UNAVAILABLE
    assert valuation.positions_market_value is None
    assert valuation.total_equity is None
    assert valuation.positions[0].valuation_status == "PRICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_partial_and_full_sell_accounting_and_history(db_session) -> None:
    await _company(db_session)
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("10000"))
    await _buy(service, portfolio.id)
    await service.sell(
        portfolio_id=portfolio.id,
        expected_revision=1,
        ticker="AAA",
        quantity=4,
        execution_price=Decimal("110"),
        trading_day=date(2025, 1, 3),
        source="MANUAL_RESEARCH",
        reason="test",
        action_id=None,
    )
    positions = await service.portfolios.list_open_positions(portfolio.id)
    assert positions[0].quantity == 6
    assert positions[0].cost_basis == Decimal("600")
    current = await service.current()
    assert current.cash_balance == Decimal("9440")
    assert current.realized_pnl == Decimal("40")
    assert current.revision == 2

    await service.sell(
        portfolio_id=portfolio.id,
        expected_revision=2,
        ticker="AAA",
        quantity=6,
        execution_price=Decimal("90"),
        trading_day=date(2025, 1, 4),
        source="MANUAL_RESEARCH",
        reason="test",
        action_id=None,
    )
    assert await service.portfolios.list_open_positions(portfolio.id) == []
    position = (await db_session.execute(select(ResearchPosition))).scalar_one()
    assert position.status == ResearchPositionStatus.CLOSED
    events = (
        (
            await db_session.execute(
                select(ResearchTradeEvent).order_by(ResearchTradeEvent.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert [item.event_type for item in events] == [
        ResearchTradeEventType.OPEN,
        ResearchTradeEventType.PARTIAL_EXIT,
        ResearchTradeEventType.FULL_EXIT,
    ]
    current = await service.current()
    assert current.cash_balance == Decimal("9980")
    assert current.realized_pnl == Decimal("-20")
    assert current.revision == 3


@pytest.mark.asyncio
async def test_failed_and_stale_mutations_create_no_event(db_session) -> None:
    await _company(db_session)
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("500"))
    portfolio_id = portfolio.id
    with pytest.raises(ValueError, match="Insufficient cash"):
        await _buy(service, portfolio_id)
    await db_session.rollback()
    assert await service.events(portfolio_id) == []

    portfolio = await service.portfolios.get(portfolio_id, for_update=True)
    assert portfolio is not None
    portfolio.cash_balance = Decimal("10000")
    await db_session.commit()
    await _buy(service, portfolio_id)
    with pytest.raises(StalePortfolioRevisionError):
        await service.sell(
            portfolio_id=portfolio_id,
            expected_revision=0,
            ticker="AAA",
            quantity=1,
            execution_price=Decimal("100"),
            trading_day=None,
            source="test",
            reason="test",
            action_id=None,
        )
    await db_session.rollback()
    assert len(await service.events(portfolio_id)) == 1
