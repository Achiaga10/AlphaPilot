import asyncio
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.routes.admin_data import (
    admin_sync_job_manager,
    get_full_sync_operation_factory,
    get_research_ticker_sync_service,
)
from alphapilot.core.config import settings
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.main import app
from alphapilot.services.admin_data import (
    AdminSyncOutcome,
    AdminSyncProgress,
    AdminTickerSyncState,
)


@pytest.mark.asyncio
async def test_admin_tools_are_disabled_by_default(client: AsyncClient) -> None:
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = False
    try:
        capability = await client.get("/api/v1/admin/data/capability")
        summary = await client.get("/api/v1/admin/data/summary")
        ticker_write = await client.post("/api/v1/admin/data/sync/ticker", json={"ticker": "SPY"})
        universe_write = await client.post("/api/v1/admin/data/sync/universe", json={})
        custom_write = await client.post(
            "/api/v1/admin/data/custom-tickers", json={"ticker": "SBET"}
        )
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous
    assert capability.status_code == 200
    assert capability.json()["enabled"] is False
    assert capability.json()["market_data_provider"] == "Alpaca"
    assert capability.json()["market_data_feed"] in {"iex", "sip"}
    assert summary.status_code == 200
    for response in (ticker_write, universe_write, custom_write):
        assert response.status_code == 403
        assert response.json() == {"detail": "Research admin tools are disabled"}


@pytest.mark.asyncio
async def test_admin_summary_reports_stored_data_freshness(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    spy = Company(ticker="SPY", name="SPY", exchange="NYSEARCA", is_active=True)
    a = Company(ticker="AAA", name="Alpha", exchange="NYSE", is_active=True)
    b = Company(ticker="BBB", name="Beta", exchange="NYSE", is_active=True)
    custom = Company(
        ticker="SBET",
        name="Custom",
        exchange="NASDAQ",
        is_active=True,
        is_custom_tracked=True,
    )
    db_session.add_all([spy, a, b, custom])
    await db_session.flush()
    db_session.add_all(
        [
            IndexConstituent(index_symbol="^GSPC", ticker="AAA", is_active=True),
            IndexConstituent(index_symbol="^GSPC", ticker="BBB", is_active=True),
            DailyCandle(
                company_id=spy.id,
                trading_day=date(2026, 8, 20),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=1,
            ),
            DailyCandle(
                company_id=a.id,
                trading_day=date(2026, 8, 19),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=1,
            ),
            DailyCandle(
                company_id=b.id,
                trading_day=date(2026, 8, 20),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=1,
            ),
            DailyCandle(
                company_id=custom.id,
                trading_day=date(2026, 8, 18),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=1,
            ),
        ]
    )
    await db_session.commit()
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = True
    try:
        response = await client.get("/api/v1/admin/data/summary")
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous
    assert response.status_code == 200
    assert response.json() == {
        "active_company_count": 4,
        "active_sp500_count": 2,
        "active_custom_tracked_count": 1,
        "latest_spy_date": "2026-08-20",
        "earliest_active_stock_latest_date": "2026-08-18",
        "latest_active_stock_latest_date": "2026-08-20",
        "stale_tracked_ticker_count": 2,
        "fresh_tracked_ticker_count": 1,
        "no_data_tracked_ticker_count": 0,
        "latest_sync_job": None,
        "last_universe_sync_at": None,
        "last_candle_sync_at": None,
        "market_data_provider": "Alpaca",
        "market_data_feed": settings.ALPACA_DATA_FEED,
    }


@pytest.mark.asyncio
async def test_known_ticker_sync_delegates_and_unknown_is_explicit(
    client: AsyncClient,
) -> None:
    class FakeTickerSync:
        def __init__(self) -> None:
            self.calls: list[tuple[str, date, date]] = []

        async def sync_detailed(
            self, ticker: str, start: date, end: date
        ) -> tuple[str, AdminTickerSyncState, None]:
            self.calls.append((ticker, start, end))
            normalized = ticker.upper()
            return (
                normalized,
                AdminTickerSyncState.SYNCED
                if normalized == "AAPL"
                else AdminTickerSyncState.COMPANY_NOT_FOUND,
                None,
            )

    fake = FakeTickerSync()
    app.dependency_overrides[get_research_ticker_sync_service] = lambda: fake
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = True
    try:
        synced = await client.post(
            "/api/v1/admin/data/sync/ticker",
            json={
                "ticker": "aapl",
                "start_date": "2026-01-01",
                "end_date": "2026-08-20",
            },
        )
        unknown = await client.post(
            "/api/v1/admin/data/sync/ticker",
            json={
                "ticker": "fake",
                "start_date": "2026-01-01",
                "end_date": "2026-08-20",
            },
        )
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous
        app.dependency_overrides.pop(get_research_ticker_sync_service, None)
    assert synced.json()["state"] == "SYNCED"
    assert unknown.json() == {
        "ticker": "FAKE",
        "state": "COMPANY_NOT_FOUND",
        "message": "Company is not stored.",
    }
    assert len(fake.calls) == 2


@pytest.mark.asyncio
async def test_full_sync_is_non_blocking_and_prevents_duplicates(
    client: AsyncClient,
) -> None:
    release = asyncio.Event()

    async def operation(progress: object) -> AdminSyncOutcome:
        assert callable(progress)
        progress(AdminSyncProgress(total=502, attempted=100, synced=99, skipped=1))
        await release.wait()
        return AdminSyncOutcome(total=502, attempted=502, synced=500, skipped=2)

    app.dependency_overrides[get_full_sync_operation_factory] = lambda: lambda request: operation
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = True
    await admin_sync_job_manager.reset()
    try:
        payload = {"start_date": "2025-01-01", "end_date": "2026-08-20"}
        first = await client.post("/api/v1/admin/data/sync/all", json=payload)
        second = await client.post("/api/v1/admin/data/sync/all", json=payload)
        assert first.status_code == 200
        assert first.json()["started"] is True
        assert second.json()["started"] is False
        assert second.json()["job"]["job_id"] == first.json()["job"]["job_id"]
        release.set()
        for _ in range(20):
            await asyncio.sleep(0)
            status = await client.get(
                f"/api/v1/admin/data/sync/jobs/{first.json()['job']['job_id']}"
            )
            if status.json()["state"] == "SUCCEEDED":
                break
        assert status.json()["state"] == "SUCCEEDED"
        assert status.json()["progress"]["synced"] == 500
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous
        app.dependency_overrides.pop(get_full_sync_operation_factory, None)
        await admin_sync_job_manager.reset()


@pytest.mark.asyncio
async def test_full_sync_failure_does_not_expose_secret_text(client: AsyncClient) -> None:
    async def operation(progress: object) -> AdminSyncOutcome:
        raise RuntimeError("ALPACA_SECRET_KEY=do-not-return")

    app.dependency_overrides[get_full_sync_operation_factory] = lambda: lambda request: operation
    previous = settings.ADMIN_TOOLS_ENABLED
    settings.ADMIN_TOOLS_ENABLED = True
    await admin_sync_job_manager.reset()
    try:
        started = await client.post(
            "/api/v1/admin/data/sync/all",
            json={"start_date": "2025-01-01", "end_date": "2026-08-20"},
        )
        job_id = started.json()["job"]["job_id"]
        for _ in range(20):
            await asyncio.sleep(0)
            status = await client.get(f"/api/v1/admin/data/sync/jobs/{job_id}")
            if status.json()["state"] == "FAILED":
                break
        body = status.json()
        assert body["state"] == "FAILED"
        assert body["error"] == "Stored-data synchronization failed. Review server logs."
        assert "do-not-return" not in status.text
    finally:
        settings.ADMIN_TOOLS_ENABLED = previous
        app.dependency_overrides.pop(get_full_sync_operation_factory, None)
        await admin_sync_job_manager.reset()
