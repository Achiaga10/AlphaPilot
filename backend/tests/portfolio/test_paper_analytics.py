from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError

from alphapilot.copilot.direct_answer import render_direct_answer
from alphapilot.copilot.intent import CopilotIntent, classify_question
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.research_portfolio import (
    PaperValidationRecord,
    PositionMonitoringSnapshot,
)
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.services.paper_analytics import ForwardPaperAnalyticsService
from alphapilot.services.paper_validation import PaperValidationService
from alphapilot.services.research_portfolio import ResearchPortfolioService


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
            open=109,
            high=111,
            low=108,
            close=110,
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
            indicator_facts={
                "ema20": "108",
                "ema50": "105",
                "strong_trend": True,
                "active_exit_policy": "HYBRID",
            },
            exit_triggered=False,
        )
    )
    await db_session.commit()
    return portfolio, position


@pytest.mark.asyncio
async def test_versioned_evidence_is_frozen_and_does_not_mutate_portfolio(db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    before = (portfolio.cash_balance, portfolio.revision, position.quantity)
    service = PaperValidationService(db_session)
    opened = await service.record_entry(
        portfolio_id=portfolio.id,
        position_id=position.id,
        actual_quantity=8,
        actual_entry_price=Decimal("101"),
        actual_entry_at=datetime(2025, 1, 3, 15, tzinfo=UTC),
        note="controlled",
    )
    assert opened.entry_evidence_schema_version == 1
    assert opened.evidence_completeness == "FULL"
    assert opened.entry_evidence is not None
    assert opened.entry_evidence["decision"]["strategy_profile_id"] == "ema20-pullback-v1"
    assert opened.entry_evidence["decision"]["source_action_id"] == "entry"
    assert opened.entry_evidence["actual_execution"]["fill_price"] == "101"
    assert opened.entry_adverse_slippage_dollars_per_share == Decimal("1")
    assert opened.quantity_adherence_percent == Decimal("80")

    closed = await service.record_exit(
        portfolio_id=portfolio.id,
        validation_id=opened.id,
        actual_exit_quantity=8,
        actual_exit_price=Decimal("110"),
        actual_exit_at=datetime(2025, 7, 1, 15, tzinfo=UTC),
        note=None,
    )
    assert closed.exit_evidence_schema_version == 1
    assert closed.exit_evidence is not None
    assert closed.exit_evidence["actual_execution"]["fill_price"] == "110"
    current = await service.portfolios.get_current()
    current_position = await service.portfolios.get_position(portfolio.id, position.id)
    assert current is not None and current_position is not None
    assert (current.cash_balance, current.revision, current_position.quantity) == before

    with pytest.raises(DBAPIError, match="entry evidence is immutable"):
        await db_session.execute(
            update(PaperValidationRecord)
            .where(PaperValidationRecord.id == opened.id)
            .values(entry_evidence={"rewritten": True})
        )
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_forward_metrics_exclude_entry_day_and_use_fixed_horizons(db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    service = PaperValidationService(db_session)
    opened = await service.record_entry(
        portfolio_id=portfolio.id,
        position_id=position.id,
        actual_quantity=8,
        actual_entry_price=Decimal("100"),
        actual_entry_at=datetime(2025, 1, 3, 15, tzinfo=UTC),
        note=None,
    )
    company_id = position.company_id
    # The entry-day extreme is deliberately excluded from MFE/MAE.
    db_session.add(
        DailyCandle(
            company_id=company_id,
            trading_day=date(2025, 1, 3),
            open=100,
            high=999,
            low=1,
            close=100,
            volume=1,
        )
    )
    for offset in range(1, 27):
        day = date(2025, 1, 3) + timedelta(days=offset)
        high = Decimal("111")
        low = Decimal("99")
        if offset == 2:  # Exit-day extremes occurred at an unknowable time.
            high, low = Decimal("999"), Decimal("1")
        elif offset == 3:  # First post-exit session.
            high, low = Decimal("130"), Decimal("80")
        db_session.add(
            DailyCandle(
                company_id=company_id,
                trading_day=day,
                open=100,
                high=high,
                low=low,
                close=110,
                volume=1,
            )
        )
    await db_session.commit()
    closed = await service.record_exit(
        portfolio_id=portfolio.id,
        validation_id=opened.id,
        actual_exit_quantity=8,
        actual_exit_price=Decimal("110"),
        actual_exit_at=datetime(2025, 1, 5, 15, tzinfo=UTC),
        note=None,
    )
    result = await ForwardPaperAnalyticsService(db_session).summary(portfolio.id)
    trade = result.closed_trades[0]
    assert trade.mfe_percent == Decimal("11.00")
    assert trade.mae_percent == Decimal("-1.00")
    assert trade.excursion_session_count == 1
    assert trade.post_exit_observations["5"]["status"] == "COMPLETE"
    assert trade.post_exit_observations["5"]["max_subsequent_high"] == "130.0000"
    assert trade.post_exit_observations["20"]["status"] == "COMPLETE"
    assert closed.paper_gross_pnl == Decimal("80")
    assert result.gross_realized_pnl == Decimal("80")
    assert result.win_rate_percent == Decimal("100")
    assert result.evidence_maturity == "VERY_LOW_SAMPLE"
    assert result.strategy_breakdown[0].expectancy_return_percent == Decimal("10.0")

    # A next-session exit has no unambiguous completed daily session to measure.
    stored = await service.portfolios.get_paper_validation(portfolio.id, opened.id)
    assert stored is not None
    stored.actual_exit_at = datetime(2025, 1, 4, 15, tzinfo=UTC)
    histories = await ForwardPaperAnalyticsService(db_session)._histories([stored])
    short_trade = ForwardPaperAnalyticsService(db_session)._trade(
        stored, histories[stored.company_id]
    )
    assert short_trade.mfe_percent is None
    assert short_trade.mae_percent is None
    assert short_trade.excursion_session_count == 0


@pytest.mark.asyncio
async def test_open_excursions_use_completed_sessions_only(db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    opened = await PaperValidationService(db_session).record_entry(
        portfolio_id=portfolio.id,
        position_id=position.id,
        actual_quantity=10,
        actual_entry_price=Decimal("100"),
        actual_entry_at=datetime(2025, 1, 3, 15, tzinfo=UTC),
        note=None,
    )
    db_session.add_all(
        [
            DailyCandle(
                company_id=position.company_id,
                trading_day=date(2025, 1, 4),
                open=100,
                high=110,
                low=95,
                close=105,
                volume=1,
            ),
            DailyCandle(
                company_id=position.company_id,
                trading_day=date(2025, 1, 5),
                open=100,
                high=999,
                low=1,
                close=500,
                volume=1,
            ),
        ]
    )
    await db_session.commit()
    policy = CompletedDailySessionPolicy(now_provider=lambda: datetime(2025, 1, 5, 17, tzinfo=UTC))
    trade = await ForwardPaperAnalyticsService(db_session, session_policy=policy).detail(
        portfolio.id, opened.id
    )
    assert trade.mfe_percent == Decimal("10.0")
    assert trade.mae_percent == Decimal("-5.00")
    assert trade.excursion_session_count == 1
    assert trade.current_completed_session == date(2025, 1, 4)


@pytest.mark.asyncio
async def test_forward_analytics_api_filters_and_unknown_detail(client, db_session) -> None:
    portfolio, position = await _managed_position(db_session)
    opened = await PaperValidationService(db_session).record_entry(
        portfolio_id=portfolio.id,
        position_id=position.id,
        actual_quantity=10,
        actual_entry_price=Decimal("100"),
        actual_entry_at=datetime(2025, 1, 3, 15, tzinfo=UTC),
        note=None,
    )
    response = await client.get(
        f"/api/v1/portfolio/{portfolio.id}/paper-analytics",
        params={"status": "OPEN", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    assert response.json()["evidence_domain"] == "FORWARD_PAPER_EVIDENCE"
    assert response.json()["open_trade_count"] == 1
    detail = await client.get(f"/api/v1/portfolio/{portfolio.id}/paper-analytics/{opened.id}")
    assert detail.status_code == 200
    missing = await client.get(
        f"/api/v1/portfolio/{portfolio.id}/paper-analytics/00000000-0000-0000-0000-000000000001"
    )
    assert missing.status_code == 404


def test_forward_paper_copilot_answer_is_deterministic_without_llm() -> None:
    assert (
        classify_question("What is my paper P&L and paper win rate?")
        == CopilotIntent.PAPER_ANALYTICS
    )
    facts = {
        "paper_analytics.summary": {
            "source": "forward_paper_analytics",
            "field": "summary",
            "label": "Forward Paper Evidence summary",
            "value": {
                "open_trade_count": 2,
                "closed_trade_count": 5,
                "gross_realized_pnl": Decimal("42.50"),
                "win_rate_percent": Decimal("60"),
                "evidence_maturity": "LOW_SAMPLE",
            },
        }
    }
    answer = render_direct_answer(CopilotIntent.PAPER_ANALYTICS, facts)
    assert "+$42.50" in answer.answer
    assert "60%" in answer.answer
    assert answer.fact_ids == ("paper_analytics.summary",)
