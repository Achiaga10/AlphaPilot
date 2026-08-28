"""Add position monitoring and reconciliation audit.

Revision ID: f41c8e2067ab
Revises: d91f32a45c7b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f41c8e2067ab"
down_revision: str | Sequence[str] | None = "d91f32a45c7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_positions",
        sa.Column("exit_triggered", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("research_positions", sa.Column("exit_triggered_on", sa.Date(), nullable=True))
    op.add_column(
        "research_positions", sa.Column("exit_trigger_reason", sa.String(80), nullable=True)
    )
    op.create_table(
        "position_monitoring_snapshots",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=False),
        sa.Column("completed_trading_day", sa.Date(), nullable=False),
        sa.Column("readiness", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("strategy_profile_id", sa.String(100), nullable=True),
        sa.Column("strategy_profile_version", sa.Integer(), nullable=True),
        sa.Column("latest_close", sa.Numeric(20, 4), nullable=True),
        sa.Column("indicator_facts", sa.JSON(), nullable=False),
        sa.Column("exit_triggered", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["research_positions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "position_id", "completed_trading_day", name="uq_position_monitoring_day"
        ),
    )
    op.create_index(
        "ix_position_monitoring_portfolio_day",
        "position_monitoring_snapshots",
        ["portfolio_id", "completed_trading_day"],
    )
    op.create_table(
        "research_reconciliation_events",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("portfolio_revision", sa.Integer(), nullable=False),
        sa.Column("cash_delta", sa.Numeric(20, 4), nullable=True),
        sa.Column("before_facts", sa.JSON(), nullable=True),
        sa.Column("after_facts", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["research_positions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reconciliation_portfolio_created",
        "research_reconciliation_events",
        ["portfolio_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reconciliation_portfolio_created", table_name="research_reconciliation_events"
    )
    op.drop_table("research_reconciliation_events")
    op.drop_index(
        "ix_position_monitoring_portfolio_day", table_name="position_monitoring_snapshots"
    )
    op.drop_table("position_monitoring_snapshots")
    op.drop_column("research_positions", "exit_trigger_reason")
    op.drop_column("research_positions", "exit_triggered_on")
    op.drop_column("research_positions", "exit_triggered")
