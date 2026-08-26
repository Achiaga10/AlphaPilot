from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from alphapilot.database.models.company import Company
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.market.dto import IndexConstituentData
from alphapilot.schemas.company import CompanyUpdate
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketBatchSyncResult,
    MarketTickerSyncResult,
)
from alphapilot.services.universe_market_sync_runner import (
    UniverseMarketSyncError,
    UniverseMarketSyncRunner,
)

logger = logging.getLogger(__name__)


class ResearchDataSummaryRepository(Protocol):
    async def count_active_companies(self) -> int: ...

    async def count_active_constituents(self, index_symbol: str) -> int: ...
    async def count_active_custom_tracked(self) -> int: ...

    async def latest_candle_date(self, ticker: str) -> date | None: ...

    async def active_tracked_latest_date_range(
        self, index_symbol: str
    ) -> tuple[date | None, date | None]: ...
    async def count_stale_tracked_tickers(
        self, index_symbol: str, benchmark_date: date | None
    ) -> int: ...
    async def count_fresh_tracked_tickers(
        self, index_symbol: str, benchmark_date: date | None
    ) -> int: ...
    async def count_no_data_tracked_tickers(self, index_symbol: str) -> int: ...


class CompanyLookup(Protocol):
    async def get_company(self, ticker: str) -> object | None: ...


class TickerMarketSync(Protocol):
    async def sync_ticker(self, ticker: str, start: date, end: date) -> MarketTickerSyncResult: ...


class UniverseMembershipSync(Protocol):
    async def sync_index(self, index_symbol: str) -> Sequence[object]: ...


class UniverseCompanyMetadataSync(Protocol):
    async def sync_companies(self, index_symbol: str) -> int: ...


class UniverseDetailsProvider(Protocol):
    async def get_index_constituent_details(
        self, index_symbol: str
    ) -> list[IndexConstituentData]: ...


class AdminUniverseRepository(Protocol):
    async def list_for_index(self, index_symbol: str) -> list[IndexConstituent]: ...
    async def sync_current(
        self, index_symbol: str, tickers: list[str]
    ) -> list[IndexConstituent]: ...


class AdminCompanyService(Protocol):
    async def get_company(self, ticker: str) -> Company | None: ...
    async def create(self, company: Company) -> Company: ...
    async def update_company(self, company_id: UUID, data: CompanyUpdate) -> Company | None: ...


class MarketTargetRepository(Protocol):
    async def list_market_sync_targets(self, index_symbol: str) -> list[str]: ...


class ExplicitMarketSync(Protocol):
    async def sync_tickers(
        self, tickers: list[str], start: date, end: date
    ) -> MarketBatchSyncResult: ...


class AdminSyncJobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AdminSyncOperationType(StrEnum):
    UNIVERSE_SYNC = "UNIVERSE_SYNC"
    MARKET_CANDLES_SYNC = "MARKET_CANDLES_SYNC"
    TICKER_SYNC = "TICKER_SYNC"
    FULL_SYNC = "FULL_SYNC"


class AdminTickerSyncState(StrEnum):
    SYNCED = "SYNCED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    COMPANY_NOT_FOUND = "COMPANY_NOT_FOUND"


@dataclass(slots=True, frozen=True)
class ResearchDataFreshness:
    active_company_count: int
    active_sp500_count: int
    active_custom_tracked_count: int
    latest_spy_date: date | None
    earliest_active_stock_latest_date: date | None
    latest_active_stock_latest_date: date | None
    stale_tracked_ticker_count: int
    fresh_tracked_ticker_count: int
    no_data_tracked_ticker_count: int


@dataclass(slots=True, frozen=True)
class AdminSyncProgress:
    total: int = 0
    attempted: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    failed_tickers: tuple[str, ...] = ()
    stage: str | None = None
    current_ticker: str | None = None


@dataclass(slots=True, frozen=True)
class AdminSyncOutcome(AdminSyncProgress):
    active_constituents: int = 0
    companies_created: int = 0
    companies_updated: int = 0
    companies_unchanged: int = 0
    memberships_added: int = 0
    memberships_removed: int = 0


@dataclass(slots=True, frozen=True)
class AdminSyncJobSnapshot:
    job_id: str
    state: AdminSyncJobState
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    start_date: date
    end_date: date
    progress: AdminSyncProgress
    operation: AdminSyncOperationType = AdminSyncOperationType.FULL_SYNC
    provider: str | None = None
    feed: str | None = None
    active_constituents: int = 0
    companies_created: int = 0
    companies_updated: int = 0
    companies_unchanged: int = 0
    memberships_added: int = 0
    memberships_removed: int = 0
    failed_stage: str | None = None
    failed_ticker: str | None = None
    error_code: str | None = None
    error: str | None = None


class AdminSyncExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        stage: str,
        ticker: str | None,
        failure: MarketBatchSyncFailure,
    ) -> None:
        super().__init__(failure.error)
        self.stage = stage
        self.ticker = ticker
        self.failure = failure


@dataclass(slots=True)
class _AdminSyncJob:
    snapshot: AdminSyncJobSnapshot


AdminSyncProgressCallback = Callable[[AdminSyncProgress], None]
AdminSyncOperation = Callable[[AdminSyncProgressCallback], Awaitable[AdminSyncOutcome]]


class ResearchDataSummaryService:
    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(self, repository: ResearchDataSummaryRepository) -> None:
        self.repository = repository

    async def get_freshness(self) -> ResearchDataFreshness:
        benchmark_date = await self.repository.latest_candle_date("SPY")
        earliest, latest = await self.repository.active_tracked_latest_date_range(
            self.SP500_INDEX_SYMBOL
        )
        return ResearchDataFreshness(
            active_company_count=await self.repository.count_active_companies(),
            active_sp500_count=await self.repository.count_active_constituents(
                self.SP500_INDEX_SYMBOL
            ),
            active_custom_tracked_count=(await self.repository.count_active_custom_tracked()),
            latest_spy_date=benchmark_date,
            earliest_active_stock_latest_date=earliest,
            latest_active_stock_latest_date=latest,
            stale_tracked_ticker_count=(
                await self.repository.count_stale_tracked_tickers(
                    self.SP500_INDEX_SYMBOL, benchmark_date
                )
            ),
            fresh_tracked_ticker_count=(
                await self.repository.count_fresh_tracked_tickers(
                    self.SP500_INDEX_SYMBOL, benchmark_date
                )
            ),
            no_data_tracked_ticker_count=(
                await self.repository.count_no_data_tracked_tickers(self.SP500_INDEX_SYMBOL)
            ),
        )


class ResearchTickerSyncService:
    def __init__(
        self,
        company_service: CompanyLookup,
        market_sync_service: TickerMarketSync,
    ) -> None:
        self.company_service = company_service
        self.market_sync_service = market_sync_service

    async def sync(self, ticker: str, start: date, end: date) -> tuple[str, AdminTickerSyncState]:
        normalized, state, _ = await self.sync_detailed(ticker, start, end)
        return normalized, state

    async def sync_detailed(
        self, ticker: str, start: date, end: date
    ) -> tuple[str, AdminTickerSyncState, MarketBatchSyncFailure | None]:
        normalized = ticker.strip().upper()
        if await self.company_service.get_company(normalized) is None:
            return normalized, AdminTickerSyncState.COMPANY_NOT_FOUND, None
        result = await self.market_sync_service.sync_ticker(normalized, start, end)
        if result.failure is not None:
            return normalized, AdminTickerSyncState.FAILED, result.failure
        if result.synced:
            return normalized, AdminTickerSyncState.SYNCED, None
        return normalized, AdminTickerSyncState.SKIPPED, None


class ResearchFullSyncService:
    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        universe_service: UniverseMembershipSync,
        company_sync_service: UniverseCompanyMetadataSync,
        market_sync_runner: UniverseMarketSyncRunner,
    ) -> None:
        self.universe_service = universe_service
        self.company_sync_service = company_sync_service
        self.market_sync_runner = market_sync_runner

    async def sync_all(
        self,
        *,
        start: date,
        end: date,
        batch_size: int,
        progress_callback: AdminSyncProgressCallback,
    ) -> AdminSyncOutcome:
        constituents = await self.universe_service.sync_index(self.SP500_INDEX_SYMBOL)
        companies_created = await self.company_sync_service.sync_companies(self.SP500_INDEX_SYMBOL)
        attempted = 0
        synced = 0
        skipped = 0
        failed_tickers: list[str] = []

        def report(batch: MarketBatchSyncResult) -> None:
            nonlocal attempted, synced, skipped
            attempted += batch.attempted
            synced += batch.synced
            skipped += batch.skipped
            failed_tickers.extend(item.ticker for item in batch.failures)
            progress_callback(
                AdminSyncProgress(
                    total=batch.total_active,
                    attempted=attempted,
                    synced=synced,
                    skipped=skipped,
                    failed=len(failed_tickers),
                    failed_tickers=tuple(failed_tickers),
                )
            )

        summary = await self.market_sync_runner.run(
            index_symbol=self.SP500_INDEX_SYMBOL,
            start=start,
            end=end,
            batch_size=batch_size,
            resume=True,
            progress_callback=report,
        )
        return AdminSyncOutcome(
            total=summary.total_active,
            attempted=summary.attempted,
            synced=summary.synced,
            skipped=summary.skipped,
            failed=len(summary.failures),
            failed_tickers=tuple(item.ticker for item in summary.failures),
            active_constituents=len(constituents),
            companies_created=companies_created,
        )


class ResearchUniverseSyncService:
    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        provider: UniverseDetailsProvider,
        universe_repository: AdminUniverseRepository,
        company_service: AdminCompanyService,
    ) -> None:
        self.provider = provider
        self.universe_repository = universe_repository
        self.company_service = company_service

    async def sync(self, progress_callback: AdminSyncProgressCallback) -> AdminSyncOutcome:
        progress_callback(AdminSyncProgress(stage="universe_discovery"))
        details = await self.provider.get_index_constituent_details(self.SP500_INDEX_SYMBOL)
        if not details:
            raise RuntimeError("Provider returned no S&P 500 constituent details")
        existing_members = await self.universe_repository.list_for_index(self.SP500_INDEX_SYMBOL)
        previous_active = {
            str(item.ticker).upper() for item in existing_members if bool(item.is_active)
        }
        requested = {item.ticker.upper() for item in details}
        created = updated = unchanged = 0
        for index, item in enumerate(details, start=1):
            company = await self.company_service.get_company(item.ticker)
            if company is None:
                await self.company_service.create(
                    Company(
                        ticker=item.ticker,
                        name=item.name,
                        exchange=item.exchange,
                        sector=item.sector,
                        industry=item.industry,
                        is_active=True,
                        is_custom_tracked=False,
                    )
                )
                created += 1
            else:
                changed = any(
                    (
                        company.name != item.name,
                        company.exchange != item.exchange,
                        company.sector != item.sector,
                        company.industry != item.industry,
                        not company.is_active,
                    )
                )
                if changed:
                    await self.company_service.update_company(
                        company.id,
                        CompanyUpdate(
                            name=item.name,
                            exchange=item.exchange,
                            sector=item.sector,
                            industry=item.industry,
                            is_active=True,
                        ),
                    )
                    updated += 1
                else:
                    unchanged += 1
            progress_callback(
                AdminSyncProgress(
                    total=len(details),
                    attempted=index,
                    synced=created + updated,
                    skipped=unchanged,
                    stage="company_metadata",
                    current_ticker=item.ticker,
                )
            )
        progress_callback(
            AdminSyncProgress(
                total=len(details),
                attempted=len(details),
                synced=created + updated,
                skipped=unchanged,
                stage="membership_sync",
            )
        )
        active = await self.universe_repository.sync_current(
            self.SP500_INDEX_SYMBOL, sorted(requested)
        )
        progress_callback(
            AdminSyncProgress(
                total=len(details),
                attempted=len(details),
                synced=created + updated,
                skipped=unchanged,
                stage="complete",
            )
        )
        return AdminSyncOutcome(
            total=len(details),
            attempted=len(details),
            synced=created + updated,
            skipped=unchanged,
            active_constituents=len(active),
            companies_created=created,
            companies_updated=updated,
            companies_unchanged=unchanged,
            memberships_added=len(requested - previous_active),
            memberships_removed=len(previous_active - requested),
            stage="complete",
        )


class ResearchMarketCandleSyncService:
    SP500_INDEX_SYMBOL = "^GSPC"
    BENCHMARK_TICKER = "SPY"

    def __init__(
        self,
        target_repository: MarketTargetRepository,
        market_sync_service: ExplicitMarketSync,
    ) -> None:
        self.target_repository = target_repository
        self.market_sync_service = market_sync_service

    async def sync(
        self,
        *,
        start: date,
        end: date,
        batch_size: int,
        progress_callback: AdminSyncProgressCallback,
    ) -> AdminSyncOutcome:
        progress_callback(
            AdminSyncProgress(total=1, stage="benchmark", current_ticker=self.BENCHMARK_TICKER)
        )
        benchmark = await self.market_sync_service.sync_tickers([self.BENCHMARK_TICKER], start, end)
        if benchmark.failures:
            raise AdminSyncExecutionError(
                stage="benchmark",
                ticker=self.BENCHMARK_TICKER,
                failure=benchmark.failures[0],
            )
        if benchmark.synced != 1:
            raise AdminSyncExecutionError(
                stage="benchmark",
                ticker=self.BENCHMARK_TICKER,
                failure=MarketBatchSyncFailure(
                    ticker=self.BENCHMARK_TICKER,
                    error="SPY benchmark synchronization returned no market data.",
                    code="BENCHMARK_DATA_UNAVAILABLE",
                    provider="Alpaca",
                ),
            )
        targets = [
            ticker
            for ticker in await self.target_repository.list_market_sync_targets(
                self.SP500_INDEX_SYMBOL
            )
            if ticker != self.BENCHMARK_TICKER
        ]
        total = len(targets) + 1
        attempted = synced = 1
        skipped = 0
        failures: list[MarketBatchSyncFailure] = []
        progress_callback(
            AdminSyncProgress(
                total=total,
                attempted=1,
                synced=1,
                stage="stock_candles",
            )
        )
        for offset in range(0, len(targets), batch_size):
            current_batch = targets[offset : offset + batch_size]
            progress_callback(
                AdminSyncProgress(
                    total=total,
                    attempted=attempted,
                    synced=synced,
                    skipped=skipped,
                    failed=len(failures),
                    failed_tickers=tuple(item.ticker for item in failures),
                    stage="stock_candles",
                    current_ticker=current_batch[0] if current_batch else None,
                )
            )
            batch = await self.market_sync_service.sync_tickers(current_batch, start, end)
            if batch.failures and batch.failures[0].code == "MARKET_DATA_FEED_NOT_AUTHORIZED":
                raise AdminSyncExecutionError(
                    stage="market_candles",
                    ticker=batch.failures[0].ticker,
                    failure=batch.failures[0],
                )
            attempted += batch.attempted
            synced += batch.synced
            skipped += batch.skipped
            failures.extend(batch.failures)
            progress_callback(
                AdminSyncProgress(
                    total=total,
                    attempted=attempted,
                    synced=synced,
                    skipped=skipped,
                    failed=len(failures),
                    failed_tickers=tuple(item.ticker for item in failures),
                    stage="stock_candles",
                    current_ticker=current_batch[-1] if current_batch else None,
                )
            )
        return AdminSyncOutcome(
            total=total,
            attempted=attempted,
            synced=synced,
            skipped=skipped,
            failed=len(failures),
            failed_tickers=tuple(item.ticker for item in failures),
            stage="complete",
        )


class AdminSyncJobManager:
    """Tracks one process-local full-universe research sync at a time."""

    ACTIVE_STATES = {AdminSyncJobState.QUEUED, AdminSyncJobState.RUNNING}

    def __init__(self) -> None:
        self._jobs: dict[str, _AdminSyncJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        start: date,
        end: date,
        operation: AdminSyncOperation,
        operation_type: AdminSyncOperationType = AdminSyncOperationType.FULL_SYNC,
        provider: str | None = None,
        feed: str | None = None,
    ) -> tuple[AdminSyncJobSnapshot, bool]:
        async with self._lock:
            active = self._latest_matching(self.ACTIVE_STATES)
            if active is not None:
                return active, False
            now = datetime.now(UTC)
            snapshot = AdminSyncJobSnapshot(
                job_id=str(uuid4()),
                state=AdminSyncJobState.QUEUED,
                requested_at=now,
                started_at=None,
                finished_at=None,
                start_date=start,
                end_date=end,
                progress=AdminSyncProgress(),
                operation=operation_type,
                provider=provider,
                feed=feed,
            )
            self._jobs[snapshot.job_id] = _AdminSyncJob(snapshot)
            task = asyncio.create_task(self._run(snapshot.job_id, operation))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return snapshot, True

    async def get(self, job_id: str) -> AdminSyncJobSnapshot | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot if job is not None else None

    async def latest(self) -> AdminSyncJobSnapshot | None:
        async with self._lock:
            return self._latest_matching(set(AdminSyncJobState))

    async def latest_for_operation(
        self, operations: set[AdminSyncOperationType]
    ) -> AdminSyncJobSnapshot | None:
        async with self._lock:
            matching = [
                job.snapshot for job in self._jobs.values() if job.snapshot.operation in operations
            ]
            return max(matching, key=lambda item: item.requested_at) if matching else None

    async def reset(self) -> None:
        async with self._lock:
            tasks = tuple(self._tasks)
            self._jobs.clear()
            self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _latest_matching(self, states: set[AdminSyncJobState]) -> AdminSyncJobSnapshot | None:
        matching = [job.snapshot for job in self._jobs.values() if job.snapshot.state in states]
        return max(matching, key=lambda item: item.requested_at) if matching else None

    async def _run(self, job_id: str, operation: AdminSyncOperation) -> None:
        await self._mutate(
            job_id,
            lambda snapshot: replace(
                snapshot,
                state=AdminSyncJobState.RUNNING,
                started_at=datetime.now(UTC),
            ),
        )

        def report(progress: AdminSyncProgress) -> None:
            job = self._jobs.get(job_id)
            if job is not None:
                job.snapshot = replace(job.snapshot, progress=progress)

        try:
            outcome = await operation(report)
        except asyncio.CancelledError:
            raise
        except UniverseMarketSyncError as exc:
            logger.exception("Research sync failed during benchmark synchronization")
            await self._record_failure(
                job_id,
                stage=exc.stage,
                ticker=exc.ticker,
                failure=exc.failure,
            )
            return
        except AdminSyncExecutionError as exc:
            logger.exception("Research sync failed during %s", exc.stage)
            await self._record_failure(
                job_id,
                stage=exc.stage,
                ticker=exc.ticker,
                failure=exc.failure,
            )
            return
        except Exception:
            logger.exception("Research full-universe sync failed")
            await self._mutate(
                job_id,
                lambda snapshot: replace(
                    snapshot,
                    state=AdminSyncJobState.FAILED,
                    finished_at=datetime.now(UTC),
                    error="Stored-data synchronization failed. Review server logs.",
                ),
            )
            return
        await self._mutate(
            job_id,
            lambda snapshot: replace(
                snapshot,
                state=AdminSyncJobState.SUCCEEDED,
                finished_at=datetime.now(UTC),
                progress=AdminSyncProgress(
                    total=outcome.total,
                    attempted=outcome.attempted,
                    synced=outcome.synced,
                    skipped=outcome.skipped,
                    failed=outcome.failed,
                    failed_tickers=outcome.failed_tickers,
                    stage=outcome.stage,
                ),
                active_constituents=outcome.active_constituents,
                companies_created=outcome.companies_created,
                companies_updated=outcome.companies_updated,
                companies_unchanged=outcome.companies_unchanged,
                memberships_added=outcome.memberships_added,
                memberships_removed=outcome.memberships_removed,
            ),
        )

    async def _record_failure(
        self,
        job_id: str,
        *,
        stage: str,
        ticker: str | None,
        failure: MarketBatchSyncFailure,
    ) -> None:
        await self._mutate(
            job_id,
            lambda snapshot: replace(
                snapshot,
                state=AdminSyncJobState.FAILED,
                finished_at=datetime.now(UTC),
                failed_stage=stage,
                failed_ticker=ticker,
                error_code=failure.code,
                provider=failure.provider or snapshot.provider,
                feed=failure.feed or snapshot.feed,
                error=failure.error,
            ),
        )

    async def _mutate(
        self,
        job_id: str,
        transform: Callable[[AdminSyncJobSnapshot], AdminSyncJobSnapshot],
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.snapshot = transform(job.snapshot)
