"""User-recorded broker execution observations linked to virtual Forward orders."""

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
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExternalActionStatus(StrEnum):
    AWAITING_ACTION = "AWAITING_ACTION"
    AWAITING_RECORD = "AWAITING_RECORD"
    PARTIALLY_RECORDED = "PARTIALLY_RECORDED"
    RECORDED = "RECORDED"
    SKIPPED = "SKIPPED"
    VIRTUAL_CANCELLED = "VIRTUAL_CANCELLED"


class ExternalReconciliationStatus(StrEnum):
    INCOMPLETE = "INCOMPLETE"
    VIRTUAL_CANCELLED = "VIRTUAL_CANCELLED"
    MISSING_RECORD = "MISSING_RECORD"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    EXECUTED_AFTER_VIRTUAL_CANCEL = "EXECUTED_AFTER_VIRTUAL_CANCEL"
    ALIGNED = "ALIGNED"
    PRICE_DIVERGENCE = "PRICE_DIVERGENCE"
    QUANTITY_DIVERGENCE = "QUANTITY_DIVERGENCE"
    PRICE_AND_QUANTITY_DIVERGENCE = "PRICE_AND_QUANTITY_DIVERGENCE"


class ExternalExecutionEventType(StrEnum):
    EXTERNAL_ACTION_READY = "EXTERNAL_ACTION_READY"
    EXTERNAL_FILL_RECORDED = "EXTERNAL_FILL_RECORDED"
    EXTERNAL_FILL_VOIDED = "EXTERNAL_FILL_VOIDED"
    EXTERNAL_ACTION_PARTIAL = "EXTERNAL_ACTION_PARTIAL"
    EXTERNAL_ACTION_RECORDED = "EXTERNAL_ACTION_RECORDED"
    EXTERNAL_ACTION_SKIPPED = "EXTERNAL_ACTION_SKIPPED"
    EXTERNAL_RECONCILIATION_UPDATED = "EXTERNAL_RECONCILIATION_UPDATED"


class ExternalExecutionCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_execution_cases"
    __table_args__ = (
        UniqueConstraint("forward_order_id", name="uq_external_case_forward_order"),
        Index("ix_external_cases_portfolio", "portfolio_id"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="RESTRICT"), nullable=False
    )
    forward_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_orders.id", ondelete="RESTRICT"), nullable=False
    )
    broker: Mapped[str] = mapped_column(String(30), nullable=False, default="ALPACA")
    provenance: Mapped[str] = mapped_column(
        String(40), nullable=False, default="MANUAL_USER_RECORDED"
    )
    recording_complete: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ExternalExecutionFill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "external_execution_fills"
    __table_args__ = (
        UniqueConstraint("case_id", "request_key", name="uq_external_fill_request"),
        CheckConstraint("quantity > 0", name="ck_external_fill_quantity_positive"),
        CheckConstraint("price > 0", name="ck_external_fill_price_positive"),
        CheckConstraint("fee IS NULL OR fee >= 0", name="ck_external_fill_fee_nonnegative"),
        Index("ix_external_fills_case_created", "case_id", "created_at"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("external_execution_cases.id", ondelete="RESTRICT"), nullable=False
    )
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    mark_complete: Mapped[bool] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    void_source: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ExternalExecutionEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "external_execution_events"
    __table_args__ = (
        UniqueConstraint("case_id", "idempotency_key", name="uq_external_event_key"),
        Index("ix_external_events_portfolio_created", "portfolio_id", "created_at"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="RESTRICT"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("external_execution_cases.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
