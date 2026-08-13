from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.dependencies.market import get_market_provider
from alphapilot.database.models.company import Company
from alphapilot.main import app
from alphapilot.market.dto.candle import MarketCandle
from alphapilot.market.providers.base import MarketProvider


class FakeMarketProvider(MarketProvider):
    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, object]:
        return {}

    async def get_history(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[MarketCandle]:
        return [
            MarketCandle(
                date=date(2026, 8, 1),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("99"),
                close=Decimal("103"),
                volume=100000,
            ),
            MarketCandle(
                date=date(2026, 8, 2),
                open=Decimal("103"),
                high=Decimal("108"),
                low=Decimal("102"),
                close=Decimal("107"),
                volume=120000,
            ),
        ]


@pytest.mark.asyncio
async def test_sync_market_data(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    ticker = f"T{uuid4().hex[:8].upper()}"

    company = Company(
        id=uuid4(),
        ticker=ticker,
        name="Test Company",
        exchange="NASDAQ",
        sector="Technology",
        industry="Software",
        is_active=True,
    )

    db_session.add(company)
    await db_session.commit()

    app.dependency_overrides[get_market_provider] = lambda: FakeMarketProvider()

    try:
        response = client.post(
            f"/api/v1/market/sync/{ticker}",
            params={
                "start": "2026-08-01",
                "end": "2026-08-02",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "synced",
            "ticker": ticker,
        }

    finally:
        app.dependency_overrides.clear()


def test_sync_market_data_company_not_found(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_market_provider] = lambda: FakeMarketProvider()

    try:
        response = client.post(
            "/api/v1/market/sync/DOESNOTEXIST",
            params={
                "start": "2026-08-01",
                "end": "2026-08-02",
            },
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Company DOESNOTEXIST not found",
        }

    finally:
        app.dependency_overrides.clear()
