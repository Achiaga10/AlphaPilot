from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from alphapilot.api.routes.portfolio import get_portfolio_decision_orchestrator
from alphapilot.main import app
from alphapilot.portfolio.decisions import PortfolioDecisionPlan
from alphapilot.portfolio.orchestration import (
    CandidateDataStatus,
    CandidateOrchestrationStatus,
    PortfolioOrchestrationResult,
)
from alphapilot.strategy.signal import Signal


@pytest.mark.asyncio
async def test_risk_config_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/risk-config")
    assert response.status_code == 200
    assert response.json()["atr_period"] == 14
    assert response.json()["risk_per_position_pct"] == "1"


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


@pytest.mark.asyncio
async def test_decision_api_validates_negative_cash(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/portfolio/decisions",
        json={"strategy": "ema20-pullback", "portfolio": {"cash": "-1"}, "candidates": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_high_level_plan_api_requires_no_enriched_candidate_facts(
    client: AsyncClient,
) -> None:
    class FakeOrchestrator:
        async def build_plan(self, **kwargs: object) -> PortfolioOrchestrationResult:
            assert "state" in kwargs
            assert "sizing_policy" in kwargs
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
                    ),
                ),
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
                "sizing_policy": "atr-volatility-normalized",
            },
        )
    finally:
        app.dependency_overrides.pop(get_portfolio_decision_orchestrator, None)
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_as_of_date"] == "2026-08-20"
    assert body["sizing_policy"] == "atr-volatility-normalized"
    assert body["candidate_statuses"][0]["status"] == "NO_ACTION"
