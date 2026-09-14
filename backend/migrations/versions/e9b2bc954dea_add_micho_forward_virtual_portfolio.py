"""Add the isolated Micho Forward virtual-portfolio lifecycle.

Revision ID: e9b2bc954dea
Revises: d3f8a1b6c204
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9b2bc954dea"
down_revision: str | Sequence[str] | None = "d3f8a1b6c204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "forward_portfolios",
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("execution_mode", sa.String(length=30), nullable=False),
        sa.Column("broker_execution_mode", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("forward_start_session", sa.Date(), nullable=False),
        sa.Column("initial_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 4), nullable=False),
        sa.Column("equity", sa.Numeric(20, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_processed_session", sa.Date(), nullable=True),
        sa.Column("last_successful_cycle", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        *_identity_columns(),
        sa.CheckConstraint("initial_cash > 0", name="ck_forward_portfolios_initial_cash_positive"),
        sa.CheckConstraint("cash_balance >= 0", name="ck_forward_portfolios_cash_nonnegative"),
        sa.CheckConstraint("equity >= 0", name="ck_forward_portfolios_equity_nonnegative"),
        sa.CheckConstraint("revision >= 0", name="ck_forward_portfolios_revision_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_forward_portfolios_live_strategy",
        "forward_portfolios",
        ["strategy_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'PAUSED')"),
    )
    op.create_table(
        "forward_cycles",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("trading_session", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("audit_facts", sa.JSON(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["portfolio_id"], ["forward_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "trading_session", name="uq_forward_cycle_session"),
    )
    op.create_index("ix_forward_cycles_portfolio_session", "forward_cycles", ["portfolio_id", "trading_session"])
    op.create_table(
        "forward_orders",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_signal_session", sa.Date(), nullable=False),
        sa.Column("planned_execution_session", sa.Date(), nullable=True),
        sa.Column("actual_execution_session", sa.Date(), nullable=True),
        sa.Column("approved_allocation", sa.Numeric(20, 4), nullable=False),
        sa.Column("planned_shares", sa.Integer(), nullable=False),
        sa.Column("filled_shares", sa.Integer(), nullable=True),
        sa.Column("raw_fill_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("modeled_fill_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("friction_bps", sa.Numeric(10, 4), nullable=False),
        sa.Column("friction_dollars", sa.Numeric(20, 4), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("ranking_score", sa.Numeric(30, 10), nullable=True),
        sa.Column("ranking_position", sa.Integer(), nullable=True),
        sa.Column("loss_control_policy", sa.String(length=100), nullable=False),
        sa.Column("loss_control_boundary", sa.Numeric(20, 4), nullable=True),
        sa.Column("loss_control_trigger", sa.String(length=100), nullable=True),
        sa.Column("risk_per_share", sa.Numeric(20, 4), nullable=True),
        sa.Column("planned_risk_dollars", sa.Numeric(20, 4), nullable=True),
        sa.Column("planned_risk_pct", sa.Numeric(20, 8), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        *_identity_columns(),
        sa.CheckConstraint("planned_shares > 0", name="ck_forward_orders_shares_positive"),
        sa.CheckConstraint("approved_allocation >= 0", name="ck_forward_orders_allocation_nonnegative"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["forward_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "company_id", "side", "source_signal_session", name="uq_forward_order_source_signal"),
    )
    op.create_index("ix_forward_orders_portfolio_status", "forward_orders", ["portfolio_id", "status"])
    op.create_index(
        "uq_forward_pending_entry_company",
        "forward_orders",
        ["portfolio_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("side = 'ENTRY' AND status = 'PENDING'"),
    )
    op.create_table(
        "forward_positions",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("entry_order_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("signal_session", sa.Date(), nullable=False),
        sa.Column("entry_session", sa.Date(), nullable=False),
        sa.Column("raw_entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("modeled_entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("entry_friction", sa.Numeric(20, 4), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 4), nullable=False),
        sa.Column("last_mark_session", sa.Date(), nullable=False),
        sa.Column("last_close", sa.Numeric(20, 4), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 4), nullable=False),
        sa.Column("unrealized_return_pct", sa.Numeric(18, 8), nullable=False),
        sa.Column("loss_control_policy", sa.String(length=100), nullable=False),
        sa.Column("loss_control_boundary", sa.Numeric(20, 4), nullable=False),
        sa.Column("loss_control_trigger", sa.String(length=100), nullable=False),
        sa.Column("loss_control_source", sa.String(length=50), nullable=False),
        sa.Column("risk_per_share", sa.Numeric(20, 4), nullable=False),
        sa.Column("planned_risk_dollars", sa.Numeric(20, 4), nullable=False),
        sa.Column("holding_sessions", sa.Integer(), nullable=False),
        sa.Column("holding_calendar_days", sa.Integer(), nullable=False),
        sa.Column("exit_signal_session", sa.Date(), nullable=True),
        sa.Column("closed_session", sa.Date(), nullable=True),
        sa.Column("management_status", sa.String(length=40), nullable=False),
        *_identity_columns(),
        sa.CheckConstraint("shares > 0", name="ck_forward_positions_shares_positive"),
        sa.CheckConstraint("modeled_entry_price > 0", name="ck_forward_positions_entry_positive"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entry_order_id"], ["forward_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["forward_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forward_positions_portfolio_status", "forward_positions", ["portfolio_id", "status"])
    op.create_index(
        "uq_forward_open_position_company",
        "forward_positions",
        ["portfolio_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.create_foreign_key(
        "fk_forward_orders_position_id",
        "forward_orders",
        "forward_positions",
        ["position_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "forward_trades",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("signal_session", sa.Date(), nullable=False),
        sa.Column("entry_session", sa.Date(), nullable=False),
        sa.Column("raw_entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("modeled_entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("entry_friction", sa.Numeric(20, 4), nullable=False),
        sa.Column("approved_allocation", sa.Numeric(20, 4), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("loss_control_policy", sa.String(length=100), nullable=False),
        sa.Column("initial_loss_control_boundary", sa.Numeric(20, 4), nullable=False),
        sa.Column("loss_control_trigger", sa.String(length=100), nullable=False),
        sa.Column("loss_control_source", sa.String(length=50), nullable=False),
        sa.Column("risk_per_share", sa.Numeric(20, 4), nullable=False),
        sa.Column("planned_risk_dollars", sa.Numeric(20, 4), nullable=False),
        sa.Column("entry_evidence", sa.JSON(), nullable=False),
        sa.Column("exit_signal_session", sa.Date(), nullable=False),
        sa.Column("exit_session", sa.Date(), nullable=False),
        sa.Column("raw_exit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("modeled_exit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("exit_friction", sa.Numeric(20, 4), nullable=False),
        sa.Column("exit_reason", sa.String(length=100), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(20, 4), nullable=False),
        sa.Column("net_pnl", sa.Numeric(20, 4), nullable=False),
        sa.Column("return_pct", sa.Numeric(20, 8), nullable=False),
        sa.Column("holding_sessions", sa.Integer(), nullable=False),
        sa.Column("holding_calendar_days", sa.Integer(), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["forward_portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["forward_positions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("position_id", name="uq_forward_trade_position"),
    )
    op.create_index("ix_forward_trades_portfolio_exit", "forward_trades", ["portfolio_id", "exit_session"])
    op.create_table(
        "forward_events",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("trading_session", sa.Date(), nullable=True),
        sa.Column("ticker", sa.String(length=10), nullable=True),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=250), nullable=False),
        sa.Column("numeric_provenance", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["forward_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "idempotency_key", name="uq_forward_event_key"),
    )
    op.create_index("ix_forward_events_portfolio_created", "forward_events", ["portfolio_id", "created_at"])
    op.create_table(
        "forward_equity_points",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("trading_session", sa.Date(), nullable=False),
        sa.Column("cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("positions_market_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("equity", sa.Numeric(20, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 4), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 4), nullable=False),
        sa.Column("open_position_count", sa.Integer(), nullable=False),
        sa.Column("exposure_pct", sa.Numeric(20, 8), nullable=False),
        *_identity_columns(),
        sa.ForeignKeyConstraint(["portfolio_id"], ["forward_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "trading_session", name="uq_forward_equity_session"),
    )
    op.create_index("ix_forward_equity_portfolio_session", "forward_equity_points", ["portfolio_id", "trading_session"])


def downgrade() -> None:
    op.drop_index("ix_forward_equity_portfolio_session", table_name="forward_equity_points")
    op.drop_table("forward_equity_points")
    op.drop_index("ix_forward_events_portfolio_created", table_name="forward_events")
    op.drop_table("forward_events")
    op.drop_index("ix_forward_trades_portfolio_exit", table_name="forward_trades")
    op.drop_table("forward_trades")
    op.drop_constraint("fk_forward_orders_position_id", "forward_orders", type_="foreignkey")
    op.drop_index("uq_forward_open_position_company", table_name="forward_positions")
    op.drop_index("ix_forward_positions_portfolio_status", table_name="forward_positions")
    op.drop_table("forward_positions")
    op.drop_index("uq_forward_pending_entry_company", table_name="forward_orders")
    op.drop_index("ix_forward_orders_portfolio_status", table_name="forward_orders")
    op.drop_table("forward_orders")
    op.drop_index("ix_forward_cycles_portfolio_session", table_name="forward_cycles")
    op.drop_table("forward_cycles")
    op.drop_index("uq_forward_portfolios_live_strategy", table_name="forward_portfolios")
    op.drop_table("forward_portfolios")
