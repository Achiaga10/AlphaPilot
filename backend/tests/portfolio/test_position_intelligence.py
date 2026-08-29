from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.research_portfolio import PositionMonitoringSnapshot
from alphapilot.services.paper_validation import PaperValidationService
from alphapilot.services.position_intelligence import PositionIntelligenceService
from alphapilot.services.research_portfolio import (
    CashAdjustmentReason,
    ExternalPositionReason,
    PositionReconciliationReason,
    ResearchPortfolioService,
)


async def _managed_position(db_session):
    company = Company(ticker="AAPL", name="Apple Inc.", exchange="NASDAQ", sector="Technology")
    db_session.add(company)
    await db_session.commit()
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("10000"))
    await service.buy(
        portfolio_id=portfolio.id,
        expected_revision=0,
        ticker="AAPL",
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
        action_id="entry",
    )
    position = (await service.portfolios.list_open_positions(portfolio.id))[0]
    db_session.add(
        DailyCandle(
            company_id=company.id,
            trading_day=date(2025, 6, 30),
            open=Decimal("109"),
            high=Decimal("111"),
            low=Decimal("108"),
            close=Decimal("110"),
            volume=100,
        )
    )
    db_session.add(
        PositionMonitoringSnapshot(
            portfolio_id=portfolio.id,
            position_id=position.id,
            completed_trading_day=date(2025, 6, 30),
            readiness="READY",
            status="HOLD",
            reason="EMA20_HELD",
            strategy_profile_id="ema20-pullback-v1",
            strategy_profile_version=1,
            latest_close=Decimal("110"),
            indicator_facts={"ema20": "108", "active_exit_policy": "HYBRID"},
            exit_triggered=False,
        )
    )
    await db_session.commit()
    return portfolio, position


@pytest.mark.asyncio
async def test_position_intelligence_composes_stored_facts_without_mutation(db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    before_revision = portfolio.revision
    result = await PositionIntelligenceService(db_session).get_position_intelligence(
        portfolio.id, position.id
    )
    assert result.strategy_profile_id == "ema20-pullback-v1"
    assert result.strategy_profile_version == 1
    assert result.entry_price == Decimal("100")
    assert result.latest_completed_close == Decimal("110")
    assert result.unrealized_pnl == Decimal("100")
    assert result.monitoring_status == "HOLD"
    assert result.indicator_facts["ema20"] == "108"
    assert result.active_exit_policy == "HYBRID exit with frozen 2% threshold"
    assert result.protective_stop_policy == "NONE"
    assert result.trailing_stop_policy == "NONE"
    assert result.profit_target_policy == "NONE"
    assert result.research_only_stop_status == "NOT_ACTIVE"
    assert result.explanation == "EMA20 is still held."
    assert (await ResearchPortfolioService(db_session).current()).revision == before_revision


@pytest.mark.asyncio
async def test_unknown_profile_never_fabricates_guidance(db_session) -> None:
    company = Company(ticker="EXT", name="External", exchange="NYSE")
    db_session.add(company)
    await db_session.commit()
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("10000"))
    await service.import_external_position(
        portfolio_id=portfolio.id,
        expected_revision=0,
        ticker="EXT",
        quantity=2,
        average_cost=Decimal("50"),
        entry_trading_day=date(2025, 1, 2),
        reason_code=ExternalPositionReason.ALPACA_PAPER_TRADE,
    )
    position = (await service.portfolios.list_open_positions(portfolio.id))[0]
    result = await PositionIntelligenceService(db_session).get_position_intelligence(
        portfolio.id, position.id
    )
    assert result.strategy_guidance_available is False
    assert result.monitoring_status is None
    assert result.active_exit_policy is None
    assert result.protective_stop_policy == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_manual_paper_entry_exit_is_decimal_and_cannot_mutate_portfolio(db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    portfolio_before = await ResearchPortfolioService(db_session).value(portfolio.id)
    papers = PaperValidationService(db_session)
    entry = await papers.record_entry(
        portfolio_id=portfolio.id,
        position_id=position.id,
        actual_quantity=10,
        actual_entry_price=Decimal("100.25"),
        actual_entry_at=datetime(2025, 1, 3, 15, tzinfo=UTC),
        note="Manual Alpaca Paper fill",
    )
    assert entry.execution_source == "ALPACA_PAPER_MANUAL"
    assert entry.actual_entry_at == datetime(2025, 1, 3, 15, tzinfo=UTC)
    assert entry.actual_entry_at.utcoffset() is not None
    assert entry.entry_fill_difference == Decimal("0.25")
    assert entry.entry_fill_difference_bps == Decimal("25.00")
    assert entry.quantity_difference == 0
    closed = await papers.record_exit(
        portfolio_id=portfolio.id,
        validation_id=entry.id,
        actual_exit_quantity=10,
        actual_exit_price=Decimal("110"),
        actual_exit_at=datetime(2025, 7, 1, 15, tzinfo=UTC),
        note=None,
    )
    assert closed.paper_gross_pnl == Decimal("97.50")
    assert closed.paper_gross_return_pct == Decimal("9.725685785536159600997506234")
    assert closed.actual_exit_at == datetime(2025, 7, 1, 15, tzinfo=UTC)
    assert closed.actual_exit_at is not None
    assert closed.actual_exit_at.utcoffset() is not None
    portfolio_after = await ResearchPortfolioService(db_session).value(portfolio.id)
    assert portfolio_after.cash == portfolio_before.cash
    assert portfolio_after.revision == portfolio_before.revision
    assert portfolio_after.positions[0].quantity == portfolio_before.positions[0].quantity
    with pytest.raises(ValueError, match="already closed"):
        await papers.record_exit(
            portfolio_id=portfolio.id,
            validation_id=entry.id,
            actual_exit_quantity=10,
            actual_exit_price=Decimal("111"),
            actual_exit_at=datetime(2025, 7, 2, 15, tzinfo=UTC),
            note=None,
        )


@pytest.mark.asyncio
async def test_structured_reconciliation_reasons_notes_and_direction(db_session) -> None:
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("1000"))
    await service.adjust_cash(
        portfolio_id=portfolio.id,
        expected_revision=0,
        delta=Decimal("100"),
        reason_code=CashAdjustmentReason.EXTERNAL_DEPOSIT,
        note="Paper cash reset",
    )
    event = (await service.reconciliation_events(portfolio.id))[0]
    assert event.reason_code == "EXTERNAL_DEPOSIT"
    assert event.note == "Paper cash reset"
    with pytest.raises(ValueError, match="positive delta"):
        await service.adjust_cash(
            portfolio_id=portfolio.id,
            expected_revision=1,
            delta=Decimal("-1"),
            reason_code=CashAdjustmentReason.EXTERNAL_DEPOSIT,
        )
    assert PositionReconciliationReason.QUANTITY_CORRECTION.value == "QUANTITY_CORRECTION"


@pytest.mark.asyncio
async def test_position_intelligence_and_paper_api_contract(client, db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    intelligence = await client.get(
        f"/api/v1/portfolio/{portfolio.id}/positions/{position.id}/intelligence"
    )
    assert intelligence.status_code == 200
    assert intelligence.json()["strategy_profile_id"] == "ema20-pullback-v1"
    assert intelligence.json()["monitoring_status"] == "HOLD"

    entry = await client.post(
        f"/api/v1/portfolio/{portfolio.id}/positions/{position.id}/paper-validations",
        json={
            "actual_quantity": 10,
            "actual_average_fill_price": "100.25",
            "actual_execution_at": "2025-01-03T15:00:00Z",
            "note": "manual paper fill",
        },
    )
    assert entry.status_code == 200
    assert entry.json()["actual_entry_at"] == "2025-01-03T15:00:00Z"
    assert Decimal(entry.json()["entry_fill_difference_bps"]) == Decimal("25")
    validation_id = entry.json()["id"]
    closed = await client.post(
        f"/api/v1/portfolio/{portfolio.id}/paper-validations/{validation_id}/exit",
        json={
            "actual_exit_quantity": 10,
            "actual_average_exit_fill": "110",
            "actual_execution_at": "2025-07-01T15:00:00Z",
            "note": None,
        },
    )
    assert closed.status_code == 200
    assert closed.json()["paper_gross_pnl"] == "97.5000"
    assert closed.json()["actual_exit_at"] == "2025-07-01T15:00:00Z"

    invalid_reason = await client.post(
        f"/api/v1/portfolio/{portfolio.id}/cash-adjustments",
        json={"expected_revision": 1, "delta": "1", "reason_code": "ARBITRARY"},
    )
    assert invalid_reason.status_code == 422


@pytest.mark.asyncio
async def test_paper_execution_timestamps_require_explicit_timezone(client, db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    response = await client.post(
        f"/api/v1/portfolio/{portfolio.id}/positions/{position.id}/paper-validations",
        json={
            "actual_quantity": 10,
            "actual_average_fill_price": "100.25",
            "actual_execution_at": "2025-01-03T15:00:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "timezone_aware"

    with pytest.raises(ValueError, match="must include a timezone offset"):
        await PaperValidationService(db_session).record_entry(
            portfolio_id=portfolio.id,
            position_id=position.id,
            actual_quantity=10,
            actual_entry_price=Decimal("100.25"),
            actual_entry_at=datetime(2025, 1, 3, 15),
            note=None,
        )


@pytest.mark.asyncio
async def test_paper_execution_columns_are_postgresql_timestamptz(db_session) -> None:
    result = await db_session.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'paper_validation_records' "
            "AND column_name IN ('actual_entry_at', 'actual_exit_at')"
        )
    )
    assert dict(result.all()) == {
        "actual_entry_at": "timestamp with time zone",
        "actual_exit_at": "timestamp with time zone",
    }
