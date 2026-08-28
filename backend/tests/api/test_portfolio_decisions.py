from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.routes.portfolio import (
    get_manual_sell_service,
    get_portfolio_decision_orchestrator,
)
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.main import app
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.actions import ManualPortfolioSellService
from alphapilot.portfolio.decisions import PortfolioDecisionPlan
from alphapilot.portfolio.orchestration import (
    CandidateDataStatus,
    CandidateOrchestrationStatus,
    PlanReadinessStatus,
    PortfolioOrchestrationResult,
    PortfolioPlanReadiness,
)
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import LatestStoredPriceService
from alphapilot.strategy.signal import Signal


@pytest.mark.asyncio
async def test_risk_config_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/risk-config")
    assert response.status_code == 200
    assert response.json()["atr_period"] == 14
    assert response.json()["risk_per_position_pct"] == "1"


@pytest.mark.asyncio
async def test_strategy_profiles_are_backend_owned(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/strategy-profiles")
    assert response.status_code == 200
    profiles = response.json()
    assert [item["profile_id"] for item in profiles] == [
        "ema20-pullback-v1",
        "micho-150-v1",
    ]
    assert profiles[0]["sizing_policy"] == "equal-slot"
    assert profiles[0]["hybrid_trend_threshold_pct"] == "2"
    assert profiles[1]["sizing_policy"] == "atr-volatility-normalized"
    assert profiles[1]["micho_entry_mode"] == "both"


@pytest.mark.asyncio
async def test_research_portfolio_initializes_once_and_is_backend_valued(
    client: AsyncClient,
) -> None:
    assert (await client.get("/api/v1/portfolio/current")).json() is None
    created = await client.post(
        "/api/v1/portfolio/initialize",
        json={"starting_cash": "100000", "imported_positions": []},
    )
    assert created.status_code == 200
    body = created.json()
    assert Decimal(body["cash"]) == Decimal("100000")
    assert Decimal(body["total_equity"]) == Decimal("100000")
    assert Decimal(body["cash_pct"]) == Decimal("100")
    assert body["revision"] == 0

    repeated = await client.post(
        "/api/v1/portfolio/initialize",
        json={"starting_cash": "1", "imported_positions": []},
    )
    assert repeated.status_code == 200
    assert repeated.json()["portfolio_id"] == body["portfolio_id"]
    assert Decimal(repeated.json()["cash"]) == Decimal("100000")


@pytest.mark.asyncio
async def test_decision_api_returns_ui_ready_reason_codes(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/portfolio/decisions",
        json={
            "strategy": "ema20-pullback",
            "strategy_parameters": {"exit_mode": "hybrid", "threshold": "2"},
            "selection_policy": "relative-strength-20",
            "portfolio": {
                "cash": "30000",
                "positions": [
                    {
                        "ticker": "AAA",
                        "shares": 300,
                        "reference_price": "100",
                        "sector": "Technology",
                        "modeled_risk_dollars": "3000",
                    },
                    {
                        "ticker": "SELL",
                        "shares": 400,
                        "reference_price": "100",
                        "sector": "Health Care",
                        "modeled_risk_dollars": "4000",
                    },
                ],
            },
            "candidates": [
                {
                    "ticker": "SELL",
                    "signal": "SELL",
                    "reference_price": "100",
                    "sector": "Health Care",
                },
                {
                    "ticker": "AAA",
                    "signal": "BUY",
                    "reference_price": "100",
                    "atr": "5",
                    "ranking_score": "1",
                    "sector": "Technology",
                },
                {
                    "ticker": "TECH",
                    "signal": "BUY",
                    "reference_price": "100",
                    "atr": "5",
                    "ranking_score": "0.9",
                    "sector": "Technology",
                },
                {
                    "ticker": "NEW",
                    "signal": "BUY",
                    "reference_price": "100",
                    "atr": "5",
                    "ranking_score": "0.8",
                    "sector": "Industrials",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    reasons = {item["ticker"]: item["reason"] for item in body["decisions"]}
    assert reasons == {
        "SELL": "SELL_APPROVED",
        "AAA": "ALREADY_HELD",
        "TECH": "SECTOR_LIMIT",
        "NEW": "BUY_APPROVED",
    }
    assert body["portfolio"]["equity"] == "100000"
    assert body["portfolio"]["cash_pct"] == "30.0"
    assert body["portfolio"]["invested_value"] == "70000"
    assert body["portfolio"]["modeled_risk_complete"] is True
    assert body["portfolio"]["positions"][0] == {
        "ticker": "AAA",
        "shares": 300,
        "reference_price": "100",
        "market_value": "30000",
        "portfolio_weight_pct": "30.0",
        "cost_basis": None,
        "sector": "Technology",
        "modeled_risk_dollars": "3000",
    }


@pytest.mark.asyncio
async def test_decision_api_validates_negative_cash(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/portfolio/decisions",
        json={"strategy": "ema20-pullback", "portfolio": {"cash": "-1"}, "candidates": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_portfolio_summary_flags_missing_existing_position_risk(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/portfolio/decisions",
        json={
            "strategy": "ema20-pullback",
            "portfolio": {
                "cash": "90000",
                "positions": [{"ticker": "AAA", "shares": 100, "reference_price": "100"}],
            },
            "candidates": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["portfolio"]["modeled_risk_complete"] is False


@pytest.mark.asyncio
async def test_high_level_plan_api_requires_no_enriched_candidate_facts(
    client: AsyncClient,
) -> None:
    class FakeOrchestrator:
        async def build_plan(self, **kwargs: object) -> PortfolioOrchestrationResult:
            assert "state" in kwargs
            assert kwargs["sizing_policy"] == "equal-slot"
            assert kwargs["exit_mode"] == "hybrid"
            assert kwargs["hybrid_trend_threshold_pct"] == Decimal("2")
            return PortfolioOrchestrationResult(
                plan=PortfolioDecisionPlan(
                    equity=Decimal("100000"),
                    cash=Decimal("100000"),
                    cash_reserve_requirement=Decimal("10000"),
                    current_portfolio_risk=Decimal("0"),
                    available_portfolio_risk=Decimal("8000"),
                    open_positions=0,
                    decisions=(),
                ),
                requested_as_of_date=date(2026, 8, 20),
                analysis_as_of_date=date(2026, 8, 20),
                statuses=(
                    CandidateOrchestrationStatus(
                        "AAA",
                        CandidateDataStatus.NO_ACTION,
                        date(2026, 8, 20),
                        Signal.HOLD,
                        "NO_PULLBACK",
                        company_name="Alpha Company",
                        company_id=uuid4(),
                    ),
                ),
                readiness=PortfolioPlanReadiness(
                    status=PlanReadinessStatus.NO_ACTION,
                    requested_tickers=1,
                    evaluated_tickers=1,
                    fresh_tickers=1,
                    stale_tickers=0,
                    no_data_tickers=0,
                    insufficient_history_tickers=0,
                    company_not_found_tickers=0,
                    buy_signals=0,
                    approved_buys=0,
                    approved_sells=0,
                    actionable_decisions=0,
                    latest_ticker_data_date=date(2026, 8, 20),
                    buy_rejections_by_reason={},
                ),
                evaluation_target_ticker="AAA",
            )

    app.dependency_overrides[get_portfolio_decision_orchestrator] = lambda: FakeOrchestrator()
    try:
        response = await client.post(
            "/api/v1/portfolio/plan",
            json={
                "strategy": "ema20-pullback",
                "portfolio": {"cash": "100000", "positions": []},
                "as_of_date": "2026-08-20",
                "tickers": ["AAA"],
            },
        )
    finally:
        app.dependency_overrides.pop(get_portfolio_decision_orchestrator, None)
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_as_of_date"] == "2026-08-20"
    assert body["sizing_policy"] == "equal-slot"
    assert body["strategy_profile"]["profile_id"] == "ema20-pullback-v1"
    assert body["candidate_statuses"][0]["status"] == "NO_ACTION"
    assert body["candidate_statuses"][0]["company_id"] is not None
    assert body["evaluation_target_ticker"] == "AAA"
    assert body["readiness"]["status"] == "NO_ACTION"
    assert body["portfolio"]["cash_pct"] == "100"
    assert body["portfolio"]["modeled_risk_complete"] is True
    assert body["portfolio"]["positions"] == []

    rejected_override = await client.post(
        "/api/v1/portfolio/plan",
        json={
            "strategy": "micho-150",
            "selection_policy": "relative-strength-20",
            "sizing_policy": "equal-slot",
            "portfolio": {"cash": "100000", "positions": []},
        },
    )
    assert rejected_override.status_code == 422
    assert rejected_override.json()["detail"][0]["type"] == "extra_forbidden"


@pytest.mark.asyncio
async def test_state_summary_and_same_plan_apply_action_are_backend_owned(
    client: AsyncClient,
) -> None:
    summary = await client.post(
        "/api/v1/portfolio/state-summary",
        json={
            "cash": "90000",
            "positions": [{"ticker": "AAA", "shares": 100, "reference_price": "100"}],
        },
    )
    assert summary.status_code == 200
    assert summary.json()["positions"][0]["market_value"] == "10000"
    assert summary.json()["positions"][0]["portfolio_weight_pct"] == "10.0"

    plan = await client.post(
        "/api/v1/portfolio/decisions",
        json={
            "strategy": "ema20-pullback",
            "sizing_policy": "equal-slot",
            "portfolio": {"cash": "100000", "positions": []},
            "candidates": [
                {
                    "ticker": "BUY",
                    "signal": "BUY",
                    "reference_price": "100",
                    "atr": "5",
                    "ranking_score": "1",
                }
            ],
        },
    )
    decision = plan.json()["decisions"][0]
    preview = await client.post(
        "/api/v1/portfolio/preview-action",
        json={
            "plan_id": "plan-test",
            "portfolio": {"cash": "100000", "positions": []},
            "decision": decision,
            "applied_action_ids": [],
            "requested_shares": 50,
            "strategy_profile_id": "ema20-pullback-v1",
            "strategy_profile_version": 1,
            "sizing_policy": "equal-slot",
        },
    )
    assert preview.status_code == 200
    assert preview.json()["applied"] is False
    assert preview.json()["validation_status"] == "VALID"
    assert preview.json()["quantity_semantics"] == "USER_QUANTITY_OVERRIDE"
    assert preview.json()["requested_allocation_dollars"] == "5000"
    assert preview.json()["cash_after"] == "95000"
    assert preview.json()["modeled_position_risk_dollars"] is None
    mismatched_profile = await client.post(
        "/api/v1/portfolio/preview-action",
        json={
            "plan_id": "plan-test",
            "portfolio": {"cash": "100000", "positions": []},
            "decision": decision,
            "applied_action_ids": [],
            "strategy_profile_id": "micho-150-v1",
            "strategy_profile_version": 1,
            "sizing_policy": "equal-slot",
        },
    )
    assert mismatched_profile.status_code == 422
    assert "authoritative strategy profile" in mismatched_profile.json()["detail"]
    applied = await client.post(
        "/api/v1/portfolio/apply-action",
        json={
            "plan_id": "plan-test",
            "portfolio": {"cash": "100000", "positions": []},
            "decision": decision,
            "applied_action_ids": [],
            "strategy_profile_id": "ema20-pullback-v1",
            "strategy_profile_version": 1,
            "sizing_policy": "equal-slot",
        },
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] is True
    assert applied.json()["cash_after"] == "90000"
    assert applied.json()["portfolio"]["positions"][0]["shares"] == 100


@pytest.mark.asyncio
async def test_persistent_action_uses_id_revision_and_makes_old_revision_stale(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    company = Company(ticker="BUY", name="Buy Corp", exchange="NYSE", sector="Technology")
    db_session.add(company)
    await db_session.flush()
    db_session.add(
        DailyCandle(
            company_id=company.id,
            trading_day=date(2025, 1, 2),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=100,
        )
    )
    await db_session.commit()
    portfolio = (
        await client.post(
            "/api/v1/portfolio/initialize",
            json={"starting_cash": "100000", "imported_positions": []},
        )
    ).json()
    decision = (
        await client.post(
            "/api/v1/portfolio/decisions",
            json={
                "strategy": "ema20-pullback",
                "sizing_policy": "equal-slot",
                "portfolio": {"cash": "100000", "positions": []},
                "candidates": [
                    {
                        "ticker": "BUY",
                        "signal": "BUY",
                        "reference_price": "100",
                        "atr": "5",
                        "ranking_score": "1",
                    }
                ],
            },
        )
    ).json()["decisions"][0]
    request = {
        "plan_id": "persistent-plan",
        "portfolio_id": portfolio["portfolio_id"],
        "portfolio_revision": 0,
        "analysis_as_of_date": "2025-01-02",
        "selection_policy": "relative-strength-20",
        "decision": decision,
        "applied_action_ids": [],
        "strategy_profile_id": "ema20-pullback-v1",
        "strategy_profile_version": 1,
        "sizing_policy": "equal-slot",
    }
    applied = await client.post("/api/v1/portfolio/apply-action", json=request)
    assert applied.status_code == 200
    assert applied.json()["portfolio_revision"] == 1
    assert applied.json()["portfolio_id"] == portfolio["portfolio_id"]
    assert "portfolio" not in request
    stale = await client.post("/api/v1/portfolio/preview-action", json=request)
    assert stale.status_code == 409


@pytest.mark.asyncio
async def test_manual_sell_uses_latest_stored_close_and_supports_partial_sale(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    company = Company(ticker="SALE", name="Sale", exchange="NYSE", is_active=True)
    db_session.add(company)
    await db_session.flush()
    db_session.add(
        DailyCandle(
            company_id=company.id,
            trading_day=date(2026, 8, 25),
            open=Decimal("104"),
            high=Decimal("106"),
            low=Decimal("103"),
            close=Decimal("105"),
            volume=100,
        )
    )
    await db_session.commit()
    portfolio = {
        "cash": "1000",
        "positions": [
            {"ticker": "SALE", "shares": 100, "reference_price": "90", "cost_basis": "70"}
        ],
    }
    price = await client.get("/api/v1/portfolio/latest-price/SALE")
    assert price.json()["ticker"] == "SALE"
    assert Decimal(price.json()["price"]) == Decimal("105")
    assert price.json()["price_date"] == "2026-08-25"
    assert price.json()["source"] == "LATEST_STORED_CANDLE"
    preview = await client.post(
        "/api/v1/portfolio/manual-sell/preview",
        json={"portfolio": portfolio, "ticker": "SALE", "shares_to_sell": 40},
    )
    assert preview.json()["applied"] is False
    assert preview.json()["reason"] == "READY"
    assert Decimal(preview.json()["gross_proceeds"]) == Decimal("4200")
    applied = await client.post(
        "/api/v1/portfolio/manual-sell",
        json={"portfolio": portfolio, "ticker": "SALE", "shares_to_sell": 40},
    )
    assert applied.json()["applied"] is True
    assert Decimal(applied.json()["cash_after"]) == Decimal("5200")
    assert applied.json()["shares_remaining"] == 60
    assert applied.json()["portfolio"]["positions"][0]["cost_basis"] == "70"


@pytest.mark.asyncio
async def test_latest_price_endpoint_returns_latest_stored_completed_close(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    company = Company(ticker="CLOSE", name="Close", exchange="NYSE", is_active=True)
    db_session.add(company)
    await db_session.flush()
    db_session.add_all(
        [
            DailyCandle(
                company_id=company.id,
                trading_day=date(2026, 8, 25),
                open=Decimal("100"),
                high=Decimal("102"),
                low=Decimal("99"),
                close=Decimal("101"),
                volume=100,
            ),
            DailyCandle(
                company_id=company.id,
                trading_day=date(2026, 8, 26),
                open=Decimal("101"),
                high=Decimal("999"),
                low=Decimal("1"),
                close=Decimal("999"),
                volume=1,
            ),
        ]
    )
    await db_session.commit()
    policy = CompletedDailySessionPolicy(
        now_provider=lambda: datetime(2026, 8, 26, 18, 0, tzinfo=UTC)
    )
    prices = LatestStoredPriceService(
        CompanyService(CompanyRepository(db_session)),
        DailyCandleRepository(db_session, policy),
    )
    app.dependency_overrides[get_manual_sell_service] = lambda: ManualPortfolioSellService(prices)
    try:
        response = await client.get("/api/v1/portfolio/latest-price/CLOSE")
    finally:
        app.dependency_overrides.pop(get_manual_sell_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "ticker": "CLOSE",
        "price": "101.0000",
        "price_date": "2026-08-25",
        "source": "LATEST_STORED_CANDLE",
    }
