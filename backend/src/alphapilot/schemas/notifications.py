"""Typed API contracts for operational notifications."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from alphapilot.database.models.notifications import (
    NotificationAttemptResult,
    NotificationChannel,
    NotificationFailureCategory,
    NotificationKind,
    NotificationPriority,
    NotificationStatus,
)

EmailAddress = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)
]


def _validate_email(value: str | None) -> str | None:
    if value is None:
        return None
    address = value.strip()
    if address.count("@") != 1:
        raise ValueError("Recipient must be a valid email address")
    local, domain = address.rsplit("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Recipient must be a valid email address")
    return address


class NotificationAttemptSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_number: int
    started_at: AwareDatetime
    completed_at: AwareDatetime
    result: NotificationAttemptResult
    failure_category: NotificationFailureCategory | None
    provider_message_reference: str | None
    duration_ms: int


class NotificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID | None
    channel: NotificationChannel
    status: NotificationStatus
    kind: NotificationKind
    priority: NotificationPriority
    transition: str
    generation: int
    recipient: str
    subject: str
    deduplication_key: str
    trading_session: date | None
    scheduled_at: AwareDatetime
    next_attempt_at: AwareDatetime
    sent_at: AwareDatetime | None
    last_attempt_at: AwareDatetime | None
    attempt_count: int
    failure_category: NotificationFailureCategory | None
    provider_message_reference: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    attempts: list[NotificationAttemptSchema] = Field(default_factory=list)


class NotificationPreferenceSchema(BaseModel):
    notifications_enabled: bool = False
    email_enabled: bool = False
    recipient: str | None = None
    warning_enabled: bool = True
    critical_enabled: bool = True
    recovery_enabled: bool = True
    daily_summary_enabled: bool = False


class NotificationPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notifications_enabled: bool
    email_enabled: bool
    recipient: EmailAddress | None
    warning_enabled: bool
    critical_enabled: bool
    recovery_enabled: bool
    daily_summary_enabled: bool

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str | None) -> str | None:
        return _validate_email(value)


class NotificationStatusSchema(BaseModel):
    enabled: bool
    email_enabled: bool
    configured: bool
    worker_running: bool
    queue_depth: int
    pending_count: int
    failed_count: int
    last_delivery_at: AwareDatetime | None
    last_error: NotificationFailureCategory | None


class NotificationTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: EmailAddress | None = None

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str | None) -> str | None:
        return _validate_email(value)
