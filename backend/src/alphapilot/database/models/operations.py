"""Durable deterministic production-operations incidents and audit events."""

from __future__ import annotations

from datetime import datetime
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
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OperationalIncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class OperationalSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class OperationalHealth(StrEnum):
    HEALTHY = "HEALTHY"
    ATTENTION = "ATTENTION"
    DEGRADED = "DEGRADED"


class OperationalSourceDomain(StrEnum):
    SYSTEM = "SYSTEM"
    MARKET_DATA = "MARKET_DATA"
    FORWARD = "FORWARD"
    EXTERNAL_EXECUTION = "EXTERNAL_EXECUTION"
    BROKER = "BROKER"
    RECONCILIATION = "RECONCILIATION"
    POSITION = "POSITION"
    NOTIFICATION = "NOTIFICATION"


class OperationalIncidentType(StrEnum):
    SCHEMA_MIGRATION_REQUIRED = "SCHEMA_MIGRATION_REQUIRED"
    FORWARD_ENGINE_FAILED = "FORWARD_ENGINE_FAILED"
    FORWARD_ENGINE_STALE = "FORWARD_ENGINE_STALE"
    FORWARD_CYCLE_FAILED = "FORWARD_CYCLE_FAILED"
    FORWARD_PENDING_SESSIONS = "FORWARD_PENDING_SESSIONS"
    FORWARD_PORTFOLIO_PAUSED = "FORWARD_PORTFOLIO_PAUSED"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    MARKET_DATA_MISSING = "MARKET_DATA_MISSING"
    MARKET_SYNC_FAILED = "MARKET_SYNC_FAILED"
    BROKER_SYNC_FAILED = "BROKER_SYNC_FAILED"
    BROKER_SYNC_STALE = "BROKER_SYNC_STALE"
    BROKER_SYNC_MISCONFIGURED = "BROKER_SYNC_MISCONFIGURED"
    BROKER_SYNC_DISABLED = "BROKER_SYNC_DISABLED"
    BROKER_ENVIRONMENT_MISMATCH = "BROKER_ENVIRONMENT_MISMATCH"
    EXTERNAL_BUY_ACTION_UPCOMING = "EXTERNAL_BUY_ACTION_UPCOMING"
    EXTERNAL_SELL_ACTION_UPCOMING = "EXTERNAL_SELL_ACTION_UPCOMING"
    EXTERNAL_ACTION_AWAITING_RECORD = "EXTERNAL_ACTION_AWAITING_RECORD"
    EXTERNAL_ACTION_OVERDUE = "EXTERNAL_ACTION_OVERDUE"
    PARTIAL_EXTERNAL_EXECUTION = "PARTIAL_EXTERNAL_EXECUTION"
    SKIPPED_EXTERNAL_EXECUTION = "SKIPPED_EXTERNAL_EXECUTION"
    MANUAL_EXIT_ACTION_REQUIRED = "MANUAL_EXIT_ACTION_REQUIRED"
    MANUAL_EXIT_ACTION_OVERDUE = "MANUAL_EXIT_ACTION_OVERDUE"
    BROKER_MATCH_AMBIGUOUS = "BROKER_MATCH_AMBIGUOUS"
    BROKER_EXECUTION_CONFLICT = "BROKER_EXECUTION_CONFLICT"
    UNMATCHED_BROKER_ACTIVITY = "UNMATCHED_BROKER_ACTIVITY"
    EXECUTED_AFTER_VIRTUAL_CANCEL = "EXECUTED_AFTER_VIRTUAL_CANCEL"
    QUANTITY_DIVERGENCE = "QUANTITY_DIVERGENCE"
    PRICE_DIVERGENCE = "PRICE_DIVERGENCE"
    POSITION_QUANTITY_DRIFT = "POSITION_QUANTITY_DRIFT"
    NOTIFICATION_DELIVERY_FAILED = "NOTIFICATION_DELIVERY_FAILED"
    NOTIFICATION_QUEUE_STALE = "NOTIFICATION_QUEUE_STALE"
    NOTIFICATION_MISCONFIGURED = "NOTIFICATION_MISCONFIGURED"


class OperationalEventType(StrEnum):
    OPENED = "OPENED"
    UPDATED = "UPDATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class OperationalIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_incidents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')",
            name="ck_operational_incident_status",
        ),
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'CRITICAL')",
            name="ck_operational_incident_severity",
        ),
        CheckConstraint("occurrence > 0", name="ck_operational_incident_occurrence_positive"),
        CheckConstraint(
            "(status = 'RESOLVED') = (active_deduplication_key IS NULL)",
            name="ck_operational_incident_active_identity",
        ),
        UniqueConstraint("active_deduplication_key", name="uq_operational_incident_active_key"),
        Index("ix_operational_incidents_status_severity", "status", "severity"),
        Index("ix_operational_incidents_source", "source_domain", "source_identity"),
    )

    incident_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(40), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(200), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(360), nullable=False)
    active_deduplication_key: Mapped[str | None] = mapped_column(String(360), nullable=True)
    occurrence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class OperationalIncidentEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "operational_incident_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('OPENED', 'UPDATED', 'ACKNOWLEDGED', 'RESOLVED')",
            name="ck_operational_incident_event_type",
        ),
        Index("ix_operational_incident_events_incident_created", "incident_id", "created_at"),
    )

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("operational_incidents.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
