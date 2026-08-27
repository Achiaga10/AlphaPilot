from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import UUIDPrimaryKeyMixin


class ResearchDatasetStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"


class ResearchDatasetProvenanceStatus(StrEnum):
    COMPLETE = "COMPLETE"
    LEGACY_PARTIAL = "LEGACY_PARTIAL"
    UNKNOWN = "UNKNOWN"


class ResearchDatasetMemberRole(StrEnum):
    UNIVERSE = "UNIVERSE"
    BENCHMARK = "BENCHMARK"


class ResearchDatasetSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "research_dataset_snapshots"
    __table_args__ = (
        Index("ix_research_dataset_snapshots_created", "created_at"),
        Index("ix_research_dataset_snapshots_status", "status"),
    )

    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ResearchDatasetStatus.DRAFT.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version_watermark_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_expectation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    feed_expectation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    adjustment: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_start: Mapped[date] = mapped_column(Date, nullable=False)
    requested_end: Mapped[date] = mapped_column(Date, nullable=False)
    benchmark_ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    universe_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    universe_member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    company_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candle_version_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    minimum_trading_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    maximum_trading_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    universe_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance_status: Mapped[str] = mapped_column(
        String(30), default=ResearchDatasetProvenanceStatus.UNKNOWN.value, nullable=False
    )
    value_reproducible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    git_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    git_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    creation_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ResearchDatasetUniverseMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "research_dataset_universe_members"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "role", "ticker_at_snapshot", name="uq_dataset_member_role_ticker"
        ),
        Index("ix_dataset_universe_members_snapshot_role", "snapshot_id", "role"),
        Index("ix_dataset_universe_members_company", "company_id"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_dataset_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    ticker_at_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    company_name_at_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange_at_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    sector_at_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    membership_source: Mapped[str] = mapped_column(String(100), nullable=False)


class ResearchDatasetCandleMember(Base):
    __tablename__ = "research_dataset_candle_members"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "company_id",
            "trading_day",
            name="uq_dataset_candle_company_day",
        ),
        Index(
            "ix_dataset_candle_members_snapshot_ticker_day",
            "snapshot_id",
            "ticker_at_snapshot",
            "trading_day",
        ),
        Index("ix_dataset_candle_members_version", "candle_version_id"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_dataset_snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    candle_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_candle_versions.id", ondelete="RESTRICT"), primary_key=True
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    ticker_at_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    trading_day: Mapped[date] = mapped_column(Date, nullable=False)
