from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import UUIDPrimaryKeyMixin


class DailyCandleVersion(UUIDPrimaryKeyMixin, Base):
    """One immutable materially distinct completed-session OHLCV observation."""

    __tablename__ = "daily_candle_versions"
    __table_args__ = (
        CheckConstraint(
            "(provenance_status = 'LEGACY_UNKNOWN' AND ingestion_batch_id IS NULL) "
            "OR (provenance_status = 'COMPLETE' AND ingestion_batch_id IS NOT NULL)",
            name="ck_candle_version_provenance_batch",
        ),
        CheckConstraint(
            "version_sequence > 0",
            name="ck_candle_version_sequence_positive",
        ),
        Index(
            "ix_daily_candle_versions_company_day_sequence",
            "company_id",
            "trading_day",
            "version_sequence",
            unique=True,
        ),
        Index("ix_daily_candle_versions_batch", "ingestion_batch_id"),
        Index("ix_daily_candle_versions_observed", "observed_at"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    trading_day: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    feed: Mapped[str] = mapped_column(String(50), nullable=False)
    provenance_status: Mapped[str] = mapped_column(String(30), nullable=False)
    ingestion_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
