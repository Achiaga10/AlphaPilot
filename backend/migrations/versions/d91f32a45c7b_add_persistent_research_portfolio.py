"""Add persistent research portfolio and trade lifecycle.

Revision ID: d91f32a45c7b
Revises: b7a9d4f2c613
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d91f32a45c7b"
down_revision: str | Sequence[str] | None = "b7a9d4f2c613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_portfolios",
        sa.Column("stable_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 4), server_default="0", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("cash_balance >= 0", name="ck_research_portfolios_cash_nonnegative"),
        sa.CheckConstraint("revision >= 0", name="ck_research_portfolios_revision_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_key"),
    )
    op.create_table(
        "research_positions",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("ticker_at_entry", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("average_entry_cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 4), nullable=False),
        sa.Column("entry_trading_day", sa.Date(), nullable=True),
        sa.Column("entry_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("strategy", sa.String(50), nullable=True),
        sa.Column("strategy_profile_id", sa.String(100), nullable=True),
        sa.Column("strategy_profile_version", sa.Integer(), nullable=True),
        sa.Column("strategy_profile_snapshot", sa.JSON(), nullable=True),
        sa.Column("selection_policy", sa.String(50), nullable=True),
        sa.Column("entry_decision", sa.String(30), nullable=True),
        sa.Column("entry_reason", sa.String(80), nullable=True),
        sa.Column("provenance_status", sa.String(30), nullable=False),
        sa.Column("modeled_risk_dollars", sa.Numeric(20, 4), server_default="0", nullable=False),
        sa.Column("closed_at_trading_day", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_research_positions_quantity_nonnegative"),
        sa.CheckConstraint(
            "average_entry_cost > 0", name="ck_research_positions_average_cost_positive"
        ),
        sa.CheckConstraint("cost_basis >= 0", name="ck_research_positions_cost_basis_nonnegative"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_positions_portfolio_status",
        "research_positions",
        ["portfolio_id", "status"],
    )
    op.create_index(
        "uq_research_positions_open_company",
        "research_positions",
        ["portfolio_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.create_table(
        "research_trade_events",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("execution_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=True),
        sa.Column("cash_effect", sa.Numeric(20, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 4), server_default="0", nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("action_id", sa.String(100), nullable=True),
        sa.Column("strategy", sa.String(50), nullable=True),
        sa.Column("strategy_profile_id", sa.String(100), nullable=True),
        sa.Column("strategy_profile_version", sa.Integer(), nullable=True),
        sa.Column("provenance_status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity > 0", name="ck_research_trade_events_quantity_positive"),
        sa.CheckConstraint("execution_price > 0", name="ck_research_trade_events_price_positive"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["research_positions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "action_id", name="uq_research_trade_event_action"),
    )
    op.create_index(
        "ix_research_trade_events_portfolio_created",
        "research_trade_events",
        ["portfolio_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_trade_events_portfolio_created", table_name="research_trade_events")
    op.drop_table("research_trade_events")
    op.drop_index("uq_research_positions_open_company", table_name="research_positions")
    op.drop_index("ix_research_positions_portfolio_status", table_name="research_positions")
    op.drop_table("research_positions")
    op.drop_table("research_portfolios")
