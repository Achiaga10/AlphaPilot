from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResearchDatasetManifestSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: UUID = Field(validation_alias="id")
    label: str | None
    status: str
    created_at: datetime
    finalized_at: datetime | None
    provider: str | None = Field(validation_alias="provider_expectation")
    feed: str | None = Field(validation_alias="feed_expectation")
    timeframe: str
    adjustment: str
    start: date = Field(validation_alias="requested_start")
    end: date = Field(validation_alias="requested_end")
    benchmark: str = Field(validation_alias="benchmark_ticker")
    universe_identifier: str
    universe_members: int = Field(validation_alias="universe_member_count")
    company_count: int
    candle_rows: int = Field(validation_alias="candle_version_count")
    minimum_trading_day: date | None
    maximum_trading_day: date | None
    dataset_sha256: str | None
    universe_sha256: str | None
    provenance_status: str
    value_reproducible: bool
    git_revision: str
    git_dirty: bool
    creation_duration_ms: int | None
    notes: str | None


class ResearchDatasetCreateSchema(BaseModel):
    label: str | None = Field(default=None, max_length=150)
    start: date
    end: date
    universe_mode: str = "CURRENT_RESEARCH_UNIVERSE"
    tickers: list[str] | None = None
    benchmark: str = "SPY"
    provider_expectation: str | None = None
    feed_expectation: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> ResearchDatasetCreateSchema:
        if self.start > self.end:
            raise ValueError("start must not exceed end")
        if self.universe_mode not in {"CURRENT_RESEARCH_UNIVERSE", "EXPLICIT_TICKERS"}:
            raise ValueError("Unsupported universe_mode")
        if self.universe_mode == "EXPLICIT_TICKERS" and not self.tickers:
            raise ValueError("tickers are required for EXPLICIT_TICKERS")
        return self


class ResearchDatasetVerificationSchema(BaseModel):
    snapshot_id: UUID
    verified: bool
    dataset_sha256: str
    universe_sha256: str
    candle_rows: int
    universe_members: int
    duration_ms: int
