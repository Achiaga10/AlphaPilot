"""Durable, observational Alpaca read-only synchronization evidence."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AlpacaEnvironment(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class BrokerSyncRunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class BrokerMatchState(StrEnum):
    UNMATCHED = "UNMATCHED"
    AUTO_MATCHED = "AUTO_MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    MANUAL_MATCHED = "MANUAL_MATCHED"
    IGNORED_EXTERNAL = "IGNORED_EXTERNAL"
    CONFLICT = "CONFLICT"


class BrokerSyncRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "broker_sync_runs"
    __table_args__ = (Index("ix_broker_sync_runs_env_started", "environment", "started_at"),)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    high_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    account_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    position_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    order_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    execution_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default=text("0")
    )


class BrokerAccountSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "broker_account_snapshots"
    __table_args__ = (UniqueConstraint("sync_run_id", name="uq_broker_account_snapshot_run"),)

    sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False)
    broker_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    buying_power: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BrokerPositionSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "broker_position_snapshots"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "symbol", name="uq_broker_position_run_symbol"),
        CheckConstraint("quantity >= 0", name="ck_broker_position_quantity_nonnegative"),
        Index("ix_broker_positions_env_symbol", "environment", "symbol"),
    )

    sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    average_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BrokerOrderObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "broker_order_observations"
    __table_args__ = (
        UniqueConstraint("environment", "broker_order_id", name="uq_broker_order_native_id"),
        Index("ix_broker_orders_env_updated", "environment", "broker_updated_at"),
    )

    last_sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False)
    broker_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    order_type: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    filled_average_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    broker_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BrokerExecution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "broker_executions"
    __table_args__ = (
        UniqueConstraint("environment", "broker_activity_id", name="uq_broker_execution_native_id"),
        CheckConstraint("quantity > 0", name="ck_broker_execution_quantity_positive"),
        CheckConstraint("price > 0", name="ck_broker_execution_price_positive"),
        CheckConstraint("fee IS NULL OR fee >= 0", name="ck_broker_execution_fee_nonnegative"),
        Index("ix_broker_executions_match_time", "match_state", "executed_at"),
        Index("ix_broker_executions_case", "external_case_id"),
    )

    first_sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provenance: Mapped[str] = mapped_column(String(40), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False)
    broker_activity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    match_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default=BrokerMatchState.UNMATCHED.value
    )
    match_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    external_case_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("external_execution_cases.id", ondelete="RESTRICT"), nullable=True
    )
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ignored_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BrokerExecutionMatchEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "broker_execution_match_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "request_key", name="uq_broker_match_event_request"),
        Index("ix_broker_match_events_execution_created", "execution_id", "created_at"),
    )

    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_executions.id", ondelete="RESTRICT"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(30), nullable=False)
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_case_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("external_execution_cases.id", ondelete="RESTRICT"), nullable=True
    )
    new_case_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("external_execution_cases.id", ondelete="RESTRICT"), nullable=True
    )
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
