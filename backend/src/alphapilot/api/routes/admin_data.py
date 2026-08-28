from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.core.config import settings
from alphapilot.core.lifespan import daily_market_scheduler
from alphapilot.database.models.company import Company
from alphapilot.database.session import AsyncSessionLocal, get_db
from alphapilot.market.providers.alpaca import AlpacaProvider
from alphapilot.market.providers.finnhub import FinnhubProvider
from alphapilot.market.providers.wikipedia import WikipediaIndexConstituentsProvider
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.repositories.market_data_ingestion import MarketDataIngestionBatchRepository
from alphapilot.repositories.research_data import ResearchDataRepository
from alphapilot.schemas.admin_data import (
    AdminCustomTickerListItemSchema,
    AdminCustomTickerRequest,
    AdminCustomTickerSchema,
    AdminDataSummarySchema,
    AdminFullSyncRequest,
    AdminFullSyncStartSchema,
    AdminSyncJobSchema,
    AdminTickerSyncRequest,
    AdminTickerSyncResponse,
    AdminToolsCapabilitySchema,
    DailySchedulerStatusSchema,
)
from alphapilot.services.admin_data import (
    AdminSyncJobManager,
    AdminSyncOperation,
    AdminSyncOperationType,
    AdminSyncOutcome,
    AdminSyncProgressCallback,
    AdminTickerSyncState,
    ResearchDataSummaryService,
    ResearchMarketCandleSyncService,
    ResearchTickerSyncService,
    ResearchUniverseSyncService,
)
from alphapilot.services.alpaca_bulk_market_sync import AlpacaBulkMarketSyncService
from alphapilot.services.company import CompanyService
from alphapilot.services.custom_ticker import CustomTickerService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService
from alphapilot.services.position_monitoring import PositionMonitoringService
from alphapilot.services.research_portfolio import ResearchPortfolioService

router = APIRouter(prefix="/admin/data", tags=["research-admin"])
admin_sync_job_manager = AdminSyncJobManager()

SyncOperationFactory = Callable[[AdminFullSyncRequest], AdminSyncOperation]
FullSyncOperationFactory = SyncOperationFactory


def require_admin_tools() -> None:
    if not settings.ADMIN_TOOLS_ENABLED:
        raise HTTPException(status_code=403, detail="Research admin tools are disabled")


def _services(
    session: AsyncSession,
) -> tuple[
    CompanyService,
    IndexConstituentRepository,
    ResearchDataRepository,
    AlpacaBulkMarketSyncService,
]:
    company_service = CompanyService(CompanyRepository(session))
    universe_repository = IndexConstituentRepository(session)
    research_repository = ResearchDataRepository(session)
    batch_service = AlpacaBulkMarketSyncService(
        provider=AlpacaProvider(),
        universe_repository=universe_repository,
        company_service=company_service,
        candle_service=DailyCandleService(DailyCandleRepository(session)),
        ingestion_batch_service=MarketDataIngestionBatchService(
            MarketDataIngestionBatchRepository(session)
        ),
    )
    return company_service, universe_repository, research_repository, batch_service


def get_research_data_summary_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchDataSummaryService:
    return ResearchDataSummaryService(ResearchDataRepository(session))


def get_research_ticker_sync_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchTickerSyncService:
    company, _, _, batch = _services(session)
    return ResearchTickerSyncService(company, batch)


def get_custom_ticker_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomTickerService:
    company, universe, research, batch = _services(session)
    return CustomTickerService(company, universe, FinnhubProvider(), batch, research)


async def _ensure_spy(company_service: CompanyService) -> None:
    if await company_service.get_company("SPY") is None:
        await company_service.create(
            Company(
                ticker="SPY",
                name="SPY Benchmark",
                exchange="NYSEARCA",
                sector="ETF",
                industry="S&P 500 Benchmark",
                is_active=True,
            )
        )


def build_universe_sync_operation(request: AdminFullSyncRequest) -> AdminSyncOperation:
    async def operation(progress: AdminSyncProgressCallback) -> AdminSyncOutcome:
        async with AsyncSessionLocal() as session:
            company, universe, _, _ = _services(session)
            return await ResearchUniverseSyncService(
                WikipediaIndexConstituentsProvider(), universe, company
            ).sync(progress)

    return operation


def build_market_sync_operation(request: AdminFullSyncRequest) -> AdminSyncOperation:
    async def operation(progress: AdminSyncProgressCallback) -> AdminSyncOutcome:
        async with AsyncSessionLocal() as session:
            company, _, research, batch = _services(session)
            await _ensure_spy(company)
            outcome = await ResearchMarketCandleSyncService(research, batch).sync(
                start=request.start_date,
                end=request.end_date,
                batch_size=request.batch_size,
                progress_callback=progress,
            )
            if outcome.failed == 0:
                portfolio = await ResearchPortfolioService(session).current()
                if portfolio is not None:
                    await PositionMonitoringService(session).monitor_portfolio(portfolio.id)
            return outcome

    return operation


def build_full_sync_operation(request: AdminFullSyncRequest) -> AdminSyncOperation:
    async def operation(progress: AdminSyncProgressCallback) -> AdminSyncOutcome:
        universe = await build_universe_sync_operation(request)(progress)
        candles = await build_market_sync_operation(request)(progress)
        return AdminSyncOutcome(
            total=universe.total + candles.total,
            attempted=universe.attempted + candles.attempted,
            synced=universe.synced + candles.synced,
            skipped=universe.skipped + candles.skipped,
            failed=candles.failed,
            failed_tickers=candles.failed_tickers,
            active_constituents=universe.active_constituents,
            companies_created=universe.companies_created,
            companies_updated=universe.companies_updated,
            companies_unchanged=universe.companies_unchanged,
            memberships_added=universe.memberships_added,
            memberships_removed=universe.memberships_removed,
        )

    return operation


def get_full_sync_operation_factory() -> FullSyncOperationFactory:
    return build_full_sync_operation


def get_universe_sync_operation_factory() -> SyncOperationFactory:
    return build_universe_sync_operation


def get_market_sync_operation_factory() -> SyncOperationFactory:
    return build_market_sync_operation


@router.get("/capability", response_model=AdminToolsCapabilitySchema)
async def get_admin_capability() -> AdminToolsCapabilitySchema:
    return AdminToolsCapabilitySchema(
        enabled=settings.ADMIN_TOOLS_ENABLED,
        warning=(
            "Research admin tools are enabled. This feature gate is not authentication."
            if settings.ADMIN_TOOLS_ENABLED
            else "Research admin tools are disabled by backend configuration."
        ),
        market_data_provider="Alpaca",
        market_data_feed=settings.ALPACA_DATA_FEED,
    )


@router.get("/scheduler", response_model=DailySchedulerStatusSchema)
async def get_daily_scheduler_status() -> DailySchedulerStatusSchema:
    return DailySchedulerStatusSchema.model_validate(
        daily_market_scheduler.status, from_attributes=True
    )


@router.get(
    "/summary",
    response_model=AdminDataSummarySchema,
)
async def get_admin_data_summary(
    service: Annotated[ResearchDataSummaryService, Depends(get_research_data_summary_service)],
) -> AdminDataSummarySchema:
    freshness = await service.get_freshness()
    latest = await admin_sync_job_manager.latest()
    universe = await admin_sync_job_manager.latest_for_operation(
        {AdminSyncOperationType.UNIVERSE_SYNC, AdminSyncOperationType.FULL_SYNC}
    )
    candles = await admin_sync_job_manager.latest_for_operation(
        {AdminSyncOperationType.MARKET_CANDLES_SYNC, AdminSyncOperationType.FULL_SYNC}
    )
    return AdminDataSummarySchema(
        active_company_count=freshness.active_company_count,
        active_sp500_count=freshness.active_sp500_count,
        active_custom_tracked_count=freshness.active_custom_tracked_count,
        latest_spy_date=freshness.latest_spy_date,
        earliest_active_stock_latest_date=freshness.earliest_active_stock_latest_date,
        latest_active_stock_latest_date=freshness.latest_active_stock_latest_date,
        stale_tracked_ticker_count=freshness.stale_tracked_ticker_count,
        fresh_tracked_ticker_count=freshness.fresh_tracked_ticker_count,
        no_data_tracked_ticker_count=freshness.no_data_tracked_ticker_count,
        latest_sync_job=AdminSyncJobSchema.from_snapshot(latest) if latest else None,
        last_universe_sync_at=(
            universe.finished_at if universe and universe.state.value == "SUCCEEDED" else None
        ),
        last_candle_sync_at=(
            candles.finished_at if candles and candles.state.value == "SUCCEEDED" else None
        ),
        market_data_provider="Alpaca",
        market_data_feed=settings.ALPACA_DATA_FEED,
    )


@router.post(
    "/sync/ticker",
    response_model=AdminTickerSyncResponse,
    dependencies=[Depends(require_admin_tools)],
)
async def sync_known_ticker(
    request: AdminTickerSyncRequest,
    service: Annotated[ResearchTickerSyncService, Depends(get_research_ticker_sync_service)],
) -> AdminTickerSyncResponse:
    _validate_range(request.start_date, request.end_date)
    ticker, state, failure = await service.sync_detailed(
        request.ticker, request.start_date, request.end_date
    )
    messages = {
        AdminTickerSyncState.SYNCED: "Stored market data synchronized.",
        AdminTickerSyncState.SKIPPED: "No market data was returned for this range.",
        AdminTickerSyncState.FAILED: (
            failure.error if failure else "Market data synchronization failed."
        ),
        AdminTickerSyncState.COMPANY_NOT_FOUND: "Company is not stored.",
    }
    return AdminTickerSyncResponse(ticker=ticker, state=state, message=messages[state])


async def _start_job(
    request: AdminFullSyncRequest,
    operation_type: AdminSyncOperationType,
    factory: SyncOperationFactory,
) -> AdminFullSyncStartSchema:
    _validate_range(request.start_date, request.end_date)
    snapshot, started = await admin_sync_job_manager.start(
        start=request.start_date,
        end=request.end_date,
        operation=factory(request),
        operation_type=operation_type,
        provider=(
            "Wikipedia" if operation_type == AdminSyncOperationType.UNIVERSE_SYNC else "Alpaca"
        ),
        feed=(
            None
            if operation_type == AdminSyncOperationType.UNIVERSE_SYNC
            else settings.ALPACA_DATA_FEED
        ),
    )
    return AdminFullSyncStartSchema(started=started, job=AdminSyncJobSchema.from_snapshot(snapshot))


@router.post(
    "/sync/universe",
    response_model=AdminFullSyncStartSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def start_universe_sync(
    request: AdminFullSyncRequest,
    factory: Annotated[SyncOperationFactory, Depends(get_universe_sync_operation_factory)],
) -> AdminFullSyncStartSchema:
    return await _start_job(request, AdminSyncOperationType.UNIVERSE_SYNC, factory)


@router.post(
    "/sync/candles",
    response_model=AdminFullSyncStartSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def start_market_candle_sync(
    request: AdminFullSyncRequest,
    factory: Annotated[SyncOperationFactory, Depends(get_market_sync_operation_factory)],
) -> AdminFullSyncStartSchema:
    return await _start_job(request, AdminSyncOperationType.MARKET_CANDLES_SYNC, factory)


@router.post(
    "/sync/all",
    response_model=AdminFullSyncStartSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def start_full_sync(
    request: AdminFullSyncRequest,
    factory: Annotated[FullSyncOperationFactory, Depends(get_full_sync_operation_factory)],
) -> AdminFullSyncStartSchema:
    return await _start_job(request, AdminSyncOperationType.FULL_SYNC, factory)


@router.get(
    "/sync/jobs/latest",
    response_model=AdminSyncJobSchema | None,
    dependencies=[Depends(require_admin_tools)],
)
async def get_latest_sync_job() -> AdminSyncJobSchema | None:
    snapshot = await admin_sync_job_manager.latest()
    return AdminSyncJobSchema.from_snapshot(snapshot) if snapshot else None


@router.get(
    "/sync/jobs/{job_id}",
    response_model=AdminSyncJobSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def get_sync_job(job_id: str) -> AdminSyncJobSchema:
    snapshot = await admin_sync_job_manager.get(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return AdminSyncJobSchema.from_snapshot(snapshot)


@router.get(
    "/custom-tickers",
    response_model=list[AdminCustomTickerListItemSchema],
    dependencies=[Depends(require_admin_tools)],
)
async def list_custom_tickers(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminCustomTickerListItemSchema]:
    company, universe, research, _ = _services(session)
    result: list[AdminCustomTickerListItemSchema] = []
    for item in await company.list_custom_tracked(active_only=False):
        count, first, latest = await research.company_candle_summary(item.ticker)
        result.append(
            AdminCustomTickerListItemSchema(
                ticker=item.ticker,
                company_name=item.name,
                exchange=item.exchange,
                sector=item.sector,
                is_custom_tracked=item.is_custom_tracked,
                is_sp500_member=await universe.is_active_member("^GSPC", item.ticker),
                stored_candle_count=count,
                first_candle_date=first,
                latest_candle_date=latest,
            )
        )
    return result


@router.post(
    "/custom-tickers",
    response_model=AdminCustomTickerSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def add_custom_ticker(
    request: AdminCustomTickerRequest,
    service: Annotated[CustomTickerService, Depends(get_custom_ticker_service)],
) -> AdminCustomTickerSchema:
    _validate_range(request.start_date, request.end_date)
    try:
        outcome = await service.add_and_sync(request.ticker, request.start_date, request.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AdminCustomTickerSchema.from_outcome(outcome)


@router.post(
    "/custom-tickers/{ticker}/deactivate",
    response_model=AdminCustomTickerSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def deactivate_custom_ticker(
    ticker: str,
    service: Annotated[CustomTickerService, Depends(get_custom_ticker_service)],
) -> AdminCustomTickerSchema:
    try:
        outcome = await service.deactivate(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AdminCustomTickerSchema.from_outcome(outcome)


def _validate_range(start: date, end: date) -> None:
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must not exceed end_date")
