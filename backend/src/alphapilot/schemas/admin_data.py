from dataclasses import asdict
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from alphapilot.services.admin_data import (
    AdminSyncJobSnapshot,
    AdminSyncJobState,
    AdminSyncOperationType,
    AdminTickerSyncState,
)
from alphapilot.services.custom_ticker import CustomTickerOutcome, CustomTickerState


def default_sync_start() -> date:
    return date.today() - timedelta(days=400)


class AdminToolsCapabilitySchema(BaseModel):
    enabled: bool
    warning: str
    market_data_provider: str
    market_data_feed: str


class AdminSyncProgressSchema(BaseModel):
    total: int
    attempted: int
    synced: int
    skipped: int
    failed: int
    failed_tickers: list[str]
    stage: str | None
    current_ticker: str | None


class AdminSyncJobSchema(BaseModel):
    job_id: str
    state: AdminSyncJobState
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    start_date: date
    end_date: date
    progress: AdminSyncProgressSchema
    operation: AdminSyncOperationType
    provider: str | None
    feed: str | None
    active_constituents: int
    companies_created: int
    companies_updated: int
    companies_unchanged: int
    memberships_added: int
    memberships_removed: int
    failed_stage: str | None
    failed_ticker: str | None
    error_code: str | None
    error: str | None

    @classmethod
    def from_snapshot(cls, value: AdminSyncJobSnapshot) -> "AdminSyncJobSchema":
        return cls(
            job_id=value.job_id,
            state=value.state,
            requested_at=value.requested_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
            start_date=value.start_date,
            end_date=value.end_date,
            progress=AdminSyncProgressSchema(
                total=value.progress.total,
                attempted=value.progress.attempted,
                synced=value.progress.synced,
                skipped=value.progress.skipped,
                failed=value.progress.failed,
                failed_tickers=list(value.progress.failed_tickers),
                stage=value.progress.stage,
                current_ticker=value.progress.current_ticker,
            ),
            operation=value.operation,
            provider=value.provider,
            feed=value.feed,
            active_constituents=value.active_constituents,
            companies_created=value.companies_created,
            companies_updated=value.companies_updated,
            companies_unchanged=value.companies_unchanged,
            memberships_added=value.memberships_added,
            memberships_removed=value.memberships_removed,
            failed_stage=value.failed_stage,
            failed_ticker=value.failed_ticker,
            error_code=value.error_code,
            error=value.error,
        )


class AdminDataSummarySchema(BaseModel):
    active_company_count: int
    active_sp500_count: int
    active_custom_tracked_count: int
    latest_spy_date: date | None
    earliest_active_stock_latest_date: date | None
    latest_active_stock_latest_date: date | None
    stale_tracked_ticker_count: int
    fresh_tracked_ticker_count: int
    no_data_tracked_ticker_count: int
    latest_sync_job: AdminSyncJobSchema | None
    last_universe_sync_at: datetime | None
    last_candle_sync_at: datetime | None
    market_data_provider: str
    market_data_feed: str


class AdminTickerSyncRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.-]+$")
    start_date: date = Field(default_factory=default_sync_start)
    end_date: date = Field(default_factory=date.today)


class AdminTickerSyncResponse(BaseModel):
    ticker: str
    state: AdminTickerSyncState
    message: str


class AdminFullSyncRequest(BaseModel):
    start_date: date = Field(default_factory=default_sync_start)
    end_date: date = Field(default_factory=date.today)
    batch_size: int = Field(default=100, gt=0, le=500)


class AdminFullSyncStartSchema(BaseModel):
    started: bool
    job: AdminSyncJobSchema


class AdminCustomTickerRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.-]+$")
    start_date: date = Field(default_factory=default_sync_start)
    end_date: date = Field(default_factory=date.today)


class AdminCustomTickerSchema(BaseModel):
    ticker: str
    state: CustomTickerState
    company_name: str | None
    exchange: str | None
    sector: str | None
    is_custom_tracked: bool
    is_sp500_member: bool
    stored_candle_count: int
    first_candle_date: date | None
    latest_candle_date: date | None
    message: str

    @classmethod
    def from_outcome(cls, value: CustomTickerOutcome) -> "AdminCustomTickerSchema":
        return cls(**asdict(value))


class AdminCustomTickerListItemSchema(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    sector: str | None
    is_custom_tracked: bool
    is_sp500_member: bool
    stored_candle_count: int
    first_candle_date: date | None
    latest_candle_date: date | None
