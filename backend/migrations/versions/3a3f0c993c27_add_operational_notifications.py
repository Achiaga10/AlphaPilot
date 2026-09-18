"""Add durable operational notifications.

Revision ID: 3a3f0c993c27
Revises: c28a0f1b2d3e
Create Date: 2026-09-16 10:24:14.900558
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3a3f0c993c27"
down_revision: str | Sequence[str] | None = "c28a0f1b2d3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("profile_key", sa.String(40), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("recipient", sa.String(320)),
        sa.Column("warning_enabled", sa.Boolean(), nullable=False),
        sa.Column("critical_enabled", sa.Boolean(), nullable=False),
        sa.Column("recovery_enabled", sa.Boolean(), nullable=False),
        sa.Column("daily_summary_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("profile_key", name="uq_notification_preference_profile"),
        sa.CheckConstraint(
            "profile_key = 'DEFAULT_OPERATOR'",
            name="ck_notification_preference_single_operator",
        ),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.UUID(),
            sa.ForeignKey("operational_incidents.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "incident_event_id",
            sa.UUID(),
            sa.ForeignKey("operational_incident_events.id", ondelete="RESTRICT"),
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("transition", sa.String(30), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text()),
        sa.Column("deduplication_key", sa.String(500), nullable=False),
        sa.Column("trading_session", sa.Date()),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failure_category", sa.String(40)),
        sa.Column("provider_message_reference", sa.String(500)),
        sa.Column("lease_token", sa.UUID()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("channel IN ('EMAIL')", name="ck_notification_channel"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DELIVERING', 'DELIVERED', 'RETRY_PENDING', "
            "'FAILED', 'CANCELLED')",
            name="ck_notification_status",
        ),
        sa.CheckConstraint(
            "kind IN ('INCIDENT', 'REMINDER', 'RECOVERY', 'DAILY_SUMMARY', 'TEST')",
            name="ck_notification_kind",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_notification_attempt_count"),
        sa.CheckConstraint("generation > 0", name="ck_notification_generation"),
        sa.UniqueConstraint("deduplication_key", name="uq_notification_deduplication_key"),
    )
    op.create_index(
        "ix_notifications_delivery_claim",
        "notifications",
        ["status", "next_attempt_at", "scheduled_at"],
    )
    op.create_index(
        "ix_notifications_incident", "notifications", ["incident_id", "created_at"]
    )
    op.create_table(
        "notification_delivery_attempts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "notification_id",
            sa.UUID(),
            sa.ForeignKey("notifications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("failure_category", sa.String(40)),
        sa.Column("provider_message_reference", sa.String(500)),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempt_number > 0", name="ck_notification_attempt_number"),
        sa.CheckConstraint(
            "result IN ('DELIVERED', 'TRANSIENT_FAILURE', 'PERMANENT_FAILURE')",
            name="ck_notification_attempt_result",
        ),
        sa.UniqueConstraint(
            "notification_id", "attempt_number", name="uq_notification_delivery_attempt"
        ),
    )
    op.create_index(
        "ix_notification_attempts_notification_started",
        "notification_delivery_attempts",
        ["notification_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_attempts_notification_started",
        table_name="notification_delivery_attempts",
    )
    op.drop_table("notification_delivery_attempts")
    op.drop_index("ix_notifications_incident", table_name="notifications")
    op.drop_index("ix_notifications_delivery_claim", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("notification_preferences")
