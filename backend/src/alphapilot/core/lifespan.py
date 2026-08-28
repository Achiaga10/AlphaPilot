from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from alphapilot.core.config import settings
from alphapilot.core.logging import configure_logging
from alphapilot.services.daily_market_scheduler import DailyMarketSyncScheduler, DailySyncStatus

daily_market_scheduler = DailyMarketSyncScheduler(
    enabled=settings.DAILY_MARKET_SYNC_ENABLED,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    configure_logging()

    print("AlphaPilot started")

    if daily_market_scheduler.status.enabled:

        async def scheduled_job() -> tuple[DailySyncStatus, str | None]:
            from alphapilot.api.routes.admin_data import build_market_sync_operation
            from alphapilot.database.session import AsyncSessionLocal
            from alphapilot.repositories.company import CompanyRepository
            from alphapilot.repositories.daily_candle import DailyCandleRepository
            from alphapilot.schemas.admin_data import AdminFullSyncRequest
            from alphapilot.services.admin_data import AdminSyncProgress

            def ignore_progress(_progress: AdminSyncProgress) -> None:
                pass

            async def latest_spy_session() -> date | None:
                async with AsyncSessionLocal() as session:
                    company = await CompanyRepository(session).get_by_ticker("SPY")
                    if company is None:
                        return None
                    candle = await DailyCandleRepository(session).get_latest(company.id)
                    return candle.trading_day if candle else None

            today = datetime.now(ZoneInfo("America/New_York")).date()
            before = await latest_spy_session()
            outcome = await build_market_sync_operation(
                AdminFullSyncRequest(
                    start_date=today - timedelta(days=7),
                    end_date=today,
                    batch_size=100,
                )
            )(ignore_progress)
            if outcome.failed:
                raise RuntimeError("Daily candle synchronization reported failures")
            after = await latest_spy_session()
            if after is None or before == after:
                return DailySyncStatus.NO_NEW_SESSION, str(after) if after else None
            return DailySyncStatus.SUCCEEDED, str(after)

        daily_market_scheduler.job = scheduled_job
    daily_market_scheduler.start()

    yield

    await daily_market_scheduler.stop()

    print("AlphaPilot stopped")
