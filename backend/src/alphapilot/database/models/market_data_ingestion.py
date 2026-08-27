from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import UUIDPrimaryKeyMixin


class IngestionBatchStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CandleProvenanceStatus(StrEnum):
    COMPLETE = "COMPLETE"
    LEGACY_UNKNOWN = "LEGACY_UNKNOWN"


class MarketDataIngestionBatch(UUIDPrimaryKeyMixin, Base):
    """Sanitized provenance for one provider request group."""

    __tablename__ = "market_data_ingestion_batches"
    __table_args__ = (
        Index("ix_market_data_ingestion_batches_created", "created_at"),
        Index("ix_market_data_ingestion_batches_provider_feed", "provider", "feed"),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    feed: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    adjustment: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_start: Mapped[date] = mapped_column(Date, nullable=False)
    requested_end: Mapped[date] = mapped_column(Date, nullable=False)
    benchmark_ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    request_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    symbols_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    symbols_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    symbols_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=IngestionBatchStatus.RUNNING.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
