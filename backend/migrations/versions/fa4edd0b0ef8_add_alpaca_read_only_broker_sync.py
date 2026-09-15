"""Add durable Alpaca read-only broker synchronization evidence.

Revision ID: fa4edd0b0ef8
Revises: f650e3a238a0
Create Date: 2026-09-15 11:19:06.050207

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fa4edd0b0ef8"
down_revision: str | Sequence[str] | None = "f650e3a238a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_sync_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("requested_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("high_watermark", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("account_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("position_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("order_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("execution_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index(
        "ix_broker_sync_runs_env_started", "broker_sync_runs", ["environment", "started_at"]
    )
    op.create_table(
        "broker_account_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("sync_run_id", sa.UUID(), sa.ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("broker_account_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("cash", sa.Numeric(24, 8), nullable=False),
        sa.Column("equity", sa.Numeric(24, 8), nullable=False),
        sa.Column("buying_power", sa.Numeric(24, 8), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sync_run_id", name="uq_broker_account_snapshot_run"),
    )
    op.create_table(
        "broker_position_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("sync_run_id", sa.UUID(), sa.ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(24, 8)),
        sa.Column("current_price", sa.Numeric(24, 8)),
        sa.Column("market_value", sa.Numeric(24, 8)),
        sa.Column("unrealized_pnl", sa.Numeric(24, 8)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_broker_position_quantity_nonnegative"),
        sa.UniqueConstraint("sync_run_id", "symbol", name="uq_broker_position_run_symbol"),
    )
    op.create_index("ix_broker_positions_env_symbol", "broker_position_snapshots", ["environment", "symbol"])
    op.create_table(
        "broker_order_observations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("last_sync_run_id", sa.UUID(), sa.ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("broker_order_id", sa.String(100), nullable=False),
        sa.Column("client_order_id", sa.String(100)),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("order_type", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8)),
        sa.Column("filled_quantity", sa.Numeric(24, 8), server_default=sa.text("0"), nullable=False),
        sa.Column("filled_average_price", sa.Numeric(24, 8)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("broker_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("environment", "broker_order_id", name="uq_broker_order_native_id"),
    )
    op.create_index("ix_broker_orders_env_updated", "broker_order_observations", ["environment", "broker_updated_at"])
    op.create_table(
        "broker_executions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("first_sync_run_id", sa.UUID(), sa.ForeignKey("broker_sync_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("broker_activity_id", sa.String(120), nullable=False),
        sa.Column("broker_order_id", sa.String(100)),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("fee", sa.Numeric(24, 8)),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_state", sa.String(30), nullable=False),
        sa.Column("match_reason", sa.String(120), nullable=False),
        sa.Column("external_case_id", sa.UUID(), sa.ForeignKey("external_execution_cases.id", ondelete="RESTRICT")),
        sa.Column("matched_at", sa.DateTime(timezone=True)),
        sa.Column("ignored_reason", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_broker_execution_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_broker_execution_price_positive"),
        sa.CheckConstraint("fee IS NULL OR fee >= 0", name="ck_broker_execution_fee_nonnegative"),
        sa.UniqueConstraint("environment", "broker_activity_id", name="uq_broker_execution_native_id"),
    )
    op.create_index("ix_broker_executions_case", "broker_executions", ["external_case_id"])
    op.create_index("ix_broker_executions_match_time", "broker_executions", ["match_state", "executed_at"])
    op.create_table(
        "broker_execution_match_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("execution_id", sa.UUID(), sa.ForeignKey("broker_executions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_state", sa.String(30), nullable=False),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("previous_case_id", sa.UUID(), sa.ForeignKey("external_execution_cases.id", ondelete="RESTRICT")),
        sa.Column("new_case_id", sa.UUID(), sa.ForeignKey("external_execution_cases.id", ondelete="RESTRICT")),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("execution_id", "request_key", name="uq_broker_match_event_request"),
    )
    op.create_index("ix_broker_match_events_execution_created", "broker_execution_match_events", ["execution_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_broker_match_events_execution_created", table_name="broker_execution_match_events")
    op.drop_table("broker_execution_match_events")
    op.drop_index("ix_broker_executions_match_time", table_name="broker_executions")
    op.drop_index("ix_broker_executions_case", table_name="broker_executions")
    op.drop_table("broker_executions")
    op.drop_index("ix_broker_orders_env_updated", table_name="broker_order_observations")
    op.drop_table("broker_order_observations")
    op.drop_index("ix_broker_positions_env_symbol", table_name="broker_position_snapshots")
    op.drop_table("broker_position_snapshots")
    op.drop_table("broker_account_snapshots")
    op.drop_index("ix_broker_sync_runs_env_started", table_name="broker_sync_runs")
    op.drop_table("broker_sync_runs")
