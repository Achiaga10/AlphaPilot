"""Durable operational-notification outbox, preferences, and delivery audit."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class NotificationChannel(StrEnum):
    EMAIL = "EMAIL"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    RETRY_PENDING = "RETRY_PENDING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationKind(StrEnum):
    INCIDENT = "INCIDENT"
    REMINDER = "REMINDER"
    RECOVERY = "RECOVERY"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    TEST = "TEST"


class NotificationPriority(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    RECOVERED = "RECOVERED"
    SUMMARY = "SUMMARY"
    TEST = "TEST"


class NotificationFailureCategory(StrEnum):
    TIMEOUT = "TIMEOUT"
    AUTHENTICATION = "AUTHENTICATION"
    CONNECTION = "CONNECTION"
    RECIPIENT_REJECTED = "RECIPIENT_REJECTED"
    CONFIGURATION = "CONFIGURATION"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class NotificationAttemptResult(StrEnum):
    DELIVERED = "DELIVERED"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('EMAIL')", name="ck_notification_channel"),
        CheckConstraint(
            "status IN ('PENDING', 'DELIVERING', 'DELIVERED', 'RETRY_PENDING', "
            "'FAILED', 'CANCELLED')",
            name="ck_notification_status",
        ),
        CheckConstraint(
            "kind IN ('INCIDENT', 'REMINDER', 'RECOVERY', 'DAILY_SUMMARY', 'TEST')",
            name="ck_notification_kind",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_notification_attempt_count"),
        CheckConstraint("generation > 0", name="ck_notification_generation"),
        UniqueConstraint("deduplication_key", name="uq_notification_deduplication_key"),
        Index("ix_notifications_delivery_claim", "status", "next_attempt_at", "scheduled_at"),
        Index("ix_notifications_incident", "incident_id", "created_at"),
    )

    incident_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("operational_incidents.id", ondelete="RESTRICT")
    )
    incident_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("operational_incident_events.id", ondelete="RESTRICT")
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    transition: Mapped[str] = mapped_column(String(30), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text)
    deduplication_key: Mapped[str] = mapped_column(String(500), nullable=False)
    trading_session: Mapped[date | None] = mapped_column(Date)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failure_category: Mapped[str | None] = mapped_column(String(40))
    provider_message_reference: Mapped[str | None] = mapped_column(String(500))
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDeliveryAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_notification_attempt_number"),
        CheckConstraint(
            "result IN ('DELIVERED', 'TRANSIENT_FAILURE', 'PERMANENT_FAILURE')",
            name="ck_notification_attempt_result",
        ),
        UniqueConstraint(
            "notification_id", "attempt_number", name="uq_notification_delivery_attempt"
        ),
        Index(
            "ix_notification_attempts_notification_started",
            "notification_id",
            "started_at",
        ),
    )

    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(40))
    provider_message_reference: Mapped[str | None] = mapped_column(String(500))
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("profile_key", name="uq_notification_preference_profile"),
        CheckConstraint(
            "profile_key = 'DEFAULT_OPERATOR'", name="ck_notification_preference_single_operator"
        ),
    )

    profile_key: Mapped[str] = mapped_column(String(40), nullable=False, default="DEFAULT_OPERATOR")
    notifications_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    email_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    recipient: Mapped[str | None] = mapped_column(String(320))
    warning_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    critical_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    recovery_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    daily_summary_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
