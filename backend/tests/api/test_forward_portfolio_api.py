from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import (
    PaperValidationRecord,
    ResearchPortfolio,
)


@pytest.mark.asyncio
async def test_forward_portfolio_api_lifecycle_and_empty_analytics(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    research_before = await db_session.scalar(select(func.count()).select_from(ResearchPortfolio))
    paper_before = await db_session.scalar(select(func.count()).select_from(PaperValidationRecord))

    missing = await client.get("/api/v1/forward-portfolio/current")
    assert missing.status_code == 200
    assert missing.json() is None

    created = await client.post(
        "/api/v1/forward-portfolio/initialize",
        json={"initial_cash": "100000", "forward_start_session": "2026-09-14"},
    )
    assert created.status_code == 201
    payload = created.json()
    portfolio_id = payload["id"]
    assert payload["strategy_id"] == "micho-150-v1"
    assert payload["strategy_version"] == 1
    assert payload["execution_mode"] == "VIRTUAL"
    assert payload["broker_execution_mode"] == "MANUAL_EXTERNAL"
    assert payload["status"] == "ACTIVE"
    assert payload["cash_balance"] == "100000.0000"
    assert payload["equity"] == "100000.0000"

    duplicate = await client.post(
        "/api/v1/forward-portfolio/initialize",
        json={"initial_cash": "1", "forward_start_session": "2026-09-14"},
    )
    assert duplicate.status_code == 409

    current = await client.get("/api/v1/forward-portfolio/current")
    assert current.status_code == 200
    assert current.json()["id"] == portfolio_id

    for resource in ("positions", "orders", "trades"):
        response = await client.get(f"/api/v1/forward-portfolio/{portfolio_id}/{resource}")
        assert response.status_code == 200
        assert response.json() == []

    events = await client.get(f"/api/v1/forward-portfolio/{portfolio_id}/events")
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == ["PORTFOLIO_INITIALIZED"]

    analytics = await client.get(f"/api/v1/forward-portfolio/{portfolio_id}/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["completed_trades"] == 0
    assert analytics.json()["win_rate_pct"] is None
    assert analytics.json()["profit_factor"] is None
    assert analytics.json()["expectancy"] is None

    health = await client.get(f"/api/v1/forward-portfolio/{portfolio_id}/health")
    assert health.status_code == 200
    assert health.json()["portfolio_status"] == "ACTIVE"
    assert health.json()["data_ready"] is False
    assert health.json()["pending_sessions"] == 0

    unconfirmed = await client.post(
        f"/api/v1/forward-portfolio/{portfolio_id}/pause",
        json={"expected_revision": 0, "confirmed": False},
    )
    assert unconfirmed.status_code == 422
    paused = await client.post(
        f"/api/v1/forward-portfolio/{portfolio_id}/pause",
        json={"expected_revision": 0, "confirmed": True},
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "PAUSED"

    resumed = await client.post(
        f"/api/v1/forward-portfolio/{portfolio_id}/resume",
        json={"expected_revision": 1, "confirmed": True},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "ACTIVE"

    triggered = await client.post(f"/api/v1/forward-portfolio/{portfolio_id}/cycles/run")
    assert triggered.status_code == 200
    assert triggered.json()["processed_sessions"] == []

    db_session.expire_all()
    research_after = await db_session.scalar(select(func.count()).select_from(ResearchPortfolio))
    paper_after = await db_session.scalar(select(func.count()).select_from(PaperValidationRecord))
    assert research_after == research_before
    assert paper_after == paper_before


@pytest.mark.asyncio
@pytest.mark.parametrize("cash", ["0", "-1", "0.00001"])
async def test_forward_portfolio_api_rejects_nonpositive_cash(
    client: AsyncClient, cash: str
) -> None:
    response = await client.post(
        "/api/v1/forward-portfolio/initialize",
        json={"initial_cash": cash, "forward_start_session": date(2026, 9, 14).isoformat()},
    )
    assert response.status_code == 422
