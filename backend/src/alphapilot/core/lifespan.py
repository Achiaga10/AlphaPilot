from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from alphapilot.core.config import settings
from alphapilot.core.logging import configure_logging
from alphapilot.services.broker_sync_scheduler import BrokerSyncScheduler
from alphapilot.services.daily_market_scheduler import DailyMarketSyncScheduler, DailySyncStatus
from alphapilot.services.forward_portfolio_scheduler import (
    ForwardPortfolioScheduler,
    ForwardSchedulerRunStatus,
)
from alphapilot.services.notification_scheduler import NotificationScheduler
from alphapilot.services.operations_scheduler import OperationsMonitorScheduler

daily_market_scheduler = DailyMarketSyncScheduler(
    enabled=settings.DAILY_MARKET_SYNC_ENABLED,
)
forward_portfolio_scheduler = ForwardPortfolioScheduler(
    enabled=settings.FORWARD_PORTFOLIO_SCHEDULER_ENABLED,
    interval_seconds=settings.FORWARD_PORTFOLIO_SCHEDULER_INTERVAL_SECONDS,
)
broker_sync_scheduler = BrokerSyncScheduler(
    enabled=settings.ALPACA_SYNC_ENABLED,
    interval_seconds=settings.ALPACA_SYNC_INTERVAL_SECONDS,
)
operations_monitor_scheduler = OperationsMonitorScheduler(
    enabled=settings.OPERATIONS_MONITOR_ENABLED,
    interval_seconds=settings.OPERATIONS_MONITOR_INTERVAL_SECONDS,
)
notification_scheduler = NotificationScheduler(
    enabled=settings.NOTIFICATIONS_ENABLED,
    interval_seconds=settings.NOTIFICATION_WORKER_INTERVAL_SECONDS,
)


def operations_scheduler_context() -> dict[str, object]:
    return {
        "market_status": daily_market_scheduler.status.last_status.value,
        "market_last_completed": (
            daily_market_scheduler.status.last_successful_completed_market_session
        ),
        "forward_initialized": True,
        "forward_running": forward_portfolio_scheduler.status.scheduler_running,
        "forward_status": forward_portfolio_scheduler.status.last_status.value,
        "broker_running": broker_sync_scheduler.status.scheduler_running,
        "operations_initialized": True,
        "operations_status": operations_monitor_scheduler.status.last_status.value,
    }


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

    if forward_portfolio_scheduler.status.enabled:

        async def forward_job() -> ForwardSchedulerRunStatus:
            from alphapilot.database.session import AsyncSessionLocal
            from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
            from alphapilot.repositories.company import CompanyRepository
            from alphapilot.repositories.daily_candle import DailyCandleRepository
            from alphapilot.repositories.index_constituent import IndexConstituentRepository
            from alphapilot.services.company import CompanyService
            from alphapilot.services.daily_candle import DailyCandleService
            from alphapilot.services.forward_portfolio import (
                ForwardPortfolioService,
                MichoForwardDecisionProvider,
            )

            async with AsyncSessionLocal() as session:
                orchestrator = PortfolioDecisionOrchestrator(
                    CompanyService(CompanyRepository(session)),
                    DailyCandleService(DailyCandleRepository(session)),
                    IndexConstituentRepository(session),
                )
                result = await ForwardPortfolioService(
                    session, MichoForwardDecisionProvider(orchestrator)
                ).run_pending()
                if result.portfolio_id is None:
                    return ForwardSchedulerRunStatus.NO_PORTFOLIO
                if not result.processed_sessions:
                    return ForwardSchedulerRunStatus.NO_NEW_SESSION
                return ForwardSchedulerRunStatus.SUCCEEDED

        forward_portfolio_scheduler.job = forward_job
    forward_portfolio_scheduler.start()

    if broker_sync_scheduler.status.enabled:

        async def broker_job() -> bool:
            from alphapilot.database.session import AsyncSessionLocal
            from alphapilot.services.broker_sync import AlpacaBrokerSyncService

            async with AsyncSessionLocal() as session:
                result = await AlpacaBrokerSyncService(session, scheduler_running=True).sync_now()
                return result.status == "SUCCEEDED"

        broker_sync_scheduler.job = broker_job
    broker_sync_scheduler.start()

    if operations_monitor_scheduler.status.enabled:

        async def operations_job() -> None:
            from alphapilot.database.session import AsyncSessionLocal
            from alphapilot.services.operations_monitor import OperationsMonitor

            async with AsyncSessionLocal() as session:
                await OperationsMonitor(
                    session,
                    scheduler_context=operations_scheduler_context,
                    monitor_running=True,
                ).evaluate()

        operations_monitor_scheduler.job = operations_job
    operations_monitor_scheduler.start()

    if notification_scheduler.status.enabled:

        async def notification_job() -> None:
            from alphapilot.database.session import AsyncSessionLocal
            from alphapilot.notifications.email import SMTPEmailProvider
            from alphapilot.services.notifications import (
                NotificationDeliveryWorker,
                NotificationService,
            )
            from alphapilot.services.operations_monitor import OperationsMonitor

            async with AsyncSessionLocal() as session:
                service = NotificationService(
                    session,
                    worker_running=True,
                )
                await service.plan_active_incidents()
                await service.plan_critical_reminders()
                preference = await service.preference()
                if preference.daily_summary_enabled:
                    summary = await OperationsMonitor(
                        session,
                        scheduler_context=operations_scheduler_context,
                        monitor_running=operations_monitor_scheduler.status.scheduler_running,
                    ).daily_summary()
                    await service.plan_daily_summary(summary)
                await NotificationDeliveryWorker(
                    session,
                    SMTPEmailProvider(),
                ).run_pending()

        notification_scheduler.job = notification_job
    notification_scheduler.start()

    yield

    await notification_scheduler.stop()
    await operations_monitor_scheduler.stop()
    await broker_sync_scheduler.stop()
    await forward_portfolio_scheduler.stop()
    await daily_market_scheduler.stop()

    print("AlphaPilot stopped")
