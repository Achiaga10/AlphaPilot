from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.core.config import settings
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.daily_candle import DailyCandleRepository


@pytest.mark.asyncio
async def test_research_dataset_api_create_list_show_and_verify(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    companies = [
        Company(ticker="AAPL", name="Apple", exchange="NASDAQ", is_active=True),
        Company(ticker="SPY", name="SPY", exchange="NYSEARCA", is_active=True),
    ]
    db_session.add_all(companies)
    await db_session.commit()
    await DailyCandleRepository(db_session).upsert_many(
        [
            DailyCandle(
                company_id=company.id,
                trading_day=date(2025, 1, 2),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000,
            )
            for company in companies
        ]
    )
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = True
    try:
        created = await client.post(
            "/api/v1/research-datasets",
            json={
                "label": "api-controlled",
                "start": "2025-01-02",
                "end": "2025-01-02",
                "universe_mode": "EXPLICIT_TICKERS",
                "tickers": ["AAPL"],
                "benchmark": "SPY",
            },
        )
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous

    assert created.status_code == 200
    manifest = created.json()
    assert manifest["label"] == "api-controlled"
    assert manifest["universe_members"] == 1
    assert manifest["candle_rows"] == 2
    assert manifest["provenance_status"] == "LEGACY_PARTIAL"
    assert manifest["value_reproducible"] is True

    listed = await client.get("/api/v1/research-datasets")
    shown = await client.get(f"/api/v1/research-datasets/{manifest['snapshot_id']}")
    verified = await client.post(f"/api/v1/research-datasets/{manifest['snapshot_id']}/verify")
    assert listed.status_code == shown.status_code == verified.status_code == 200
    assert listed.json()[0]["snapshot_id"] == manifest["snapshot_id"]
    assert shown.json()["dataset_sha256"] == manifest["dataset_sha256"]
    assert verified.json()["verified"] is True
    assert verified.json()["dataset_sha256"] == manifest["dataset_sha256"]


@pytest.mark.asyncio
async def test_research_dataset_create_requires_admin_tools(client: AsyncClient) -> None:
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = False
    try:
        response = await client.post(
            "/api/v1/research-datasets",
            json={
                "start": "2025-01-02",
                "end": "2025-01-02",
                "universe_mode": "EXPLICIT_TICKERS",
                "tickers": ["AAPL"],
            },
        )
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous
    assert response.status_code == 403
