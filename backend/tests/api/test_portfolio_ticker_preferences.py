from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.research_portfolio import PortfolioTickerPreference


@pytest.mark.asyncio
async def test_exclude_and_restore_ticker_are_persistent_revision_safe_preferences(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    company = Company(
        ticker="UBER", name="Uber Technologies", exchange="NYSE", sector="Industrials"
    )
    db_session.add(company)
    await db_session.commit()
    portfolio = (
        await client.post(
            "/api/v1/portfolio/initialize",
            json={"starting_cash": str(Decimal("100000")), "imported_positions": []},
        )
    ).json()
    portfolio_id = portfolio["portfolio_id"]

    excluded = await client.put(
        f"/api/v1/portfolio/{portfolio_id}/excluded-tickers/UBER",
        json={"expected_revision": 0, "reason": "User sold and wants no new recommendation"},
    )
    assert excluded.status_code == 200
    assert excluded.json()["preference"]["recommendation_status"] == "USER_EXCLUDED"
    assert excluded.json()["portfolio_revision"] == 1

    listing = await client.get(f"/api/v1/portfolio/{portfolio_id}/excluded-tickers")
    assert listing.status_code == 200
    assert [item["ticker"] for item in listing.json()] == ["UBER"]
    assert (await db_session.execute(select(PortfolioTickerPreference))).scalar_one() is not None
    persisted_company = (
        await db_session.execute(select(Company).where(Company.ticker == "UBER"))
    ).scalar_one()
    assert persisted_company.id == company.id

    stale = await client.post(
        f"/api/v1/portfolio/{portfolio_id}/excluded-tickers/UBER/restore",
        json={"expected_revision": 0},
    )
    assert stale.status_code == 409

    restored = await client.post(
        f"/api/v1/portfolio/{portfolio_id}/excluded-tickers/UBER/restore",
        json={"expected_revision": 1},
    )
    assert restored.status_code == 200
    assert restored.json()["preference"]["recommendation_status"] == "ELIGIBLE"
    assert restored.json()["portfolio_revision"] == 2
    assert (await client.get(f"/api/v1/portfolio/{portfolio_id}/excluded-tickers")).json() == []
