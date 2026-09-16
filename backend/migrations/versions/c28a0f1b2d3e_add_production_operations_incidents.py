"""Add deterministic production operations incidents.

Revision ID: c28a0f1b2d3e
Revises: fa4edd0b0ef8
Create Date: 2026-09-15 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c28a0f1b2d3e"
down_revision: str | Sequence[str] | None = "fa4edd0b0ef8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_incidents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("incident_type", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_domain", sa.String(40), nullable=False),
        sa.Column("source_identity", sa.String(200), nullable=False),
        sa.Column("deduplication_key", sa.String(360), nullable=False),
        sa.Column("active_deduplication_key", sa.String(360)),
        sa.Column("occurrence", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "active_deduplication_key",
            name="uq_operational_incident_active_key",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')",
            name="ck_operational_incident_status",
        ),
        sa.CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'CRITICAL')",
            name="ck_operational_incident_severity",
        ),
        sa.CheckConstraint(
            "occurrence > 0",
            name="ck_operational_incident_occurrence_positive",
        ),
        sa.CheckConstraint(
            "(status = 'RESOLVED') = (active_deduplication_key IS NULL)",
            name="ck_operational_incident_active_identity",
        ),
    )
    op.create_index(
        "ix_operational_incidents_status_severity",
        "operational_incidents",
        ["status", "severity"],
    )
    op.create_index(
        "ix_operational_incidents_source",
        "operational_incidents",
        ["source_domain", "source_identity"],
    )
    op.create_table(
        "operational_incident_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.UUID(),
            sa.ForeignKey("operational_incidents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('OPENED', 'UPDATED', 'ACKNOWLEDGED', 'RESOLVED')",
            name="ck_operational_incident_event_type",
        ),
    )
    op.create_index(
        "ix_operational_incident_events_incident_created",
        "operational_incident_events",
        ["incident_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_incident_events_incident_created",
        table_name="operational_incident_events",
    )
    op.drop_table("operational_incident_events")
    op.drop_index("ix_operational_incidents_source", table_name="operational_incidents")
    op.drop_index(
        "ix_operational_incidents_status_severity",
        table_name="operational_incidents",
    )
    op.drop_table("operational_incidents")
