"""Add paper validation and structured reconciliation reasons.

Revision ID: a18c4d9e2f70
Revises: f41c8e2067ab
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a18c4d9e2f70"
down_revision: str | Sequence[str] | None = "f41c8e2067ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_reconciliation_events", sa.Column("reason_code", sa.String(60), nullable=True)
    )
    op.add_column(
        "research_reconciliation_events", sa.Column("note", sa.String(500), nullable=True)
    )
    op.create_table(
        "paper_validation_records",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("execution_source", sa.String(40), nullable=False),
        sa.Column("position_provenance", sa.String(30), nullable=False),
        sa.Column("strategy", sa.String(50), nullable=True),
        sa.Column("strategy_profile_id", sa.String(100), nullable=True),
        sa.Column("strategy_profile_version", sa.Integer(), nullable=True),
        sa.Column("entry_decision", sa.String(30), nullable=True),
        sa.Column("entry_reason", sa.String(80), nullable=True),
        sa.Column("recommendation_day", sa.Date(), nullable=True),
        sa.Column("planned_quantity", sa.Integer(), nullable=True),
        sa.Column("reference_entry_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("actual_quantity", sa.Integer(), nullable=False),
        sa.Column("actual_entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("actual_entry_at", sa.DateTime(), nullable=False),
        sa.Column("entry_note", sa.String(500), nullable=True),
        sa.Column("actual_exit_quantity", sa.Integer(), nullable=True),
        sa.Column("actual_exit_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("actual_exit_at", sa.DateTime(), nullable=True),
        sa.Column("exit_note", sa.String(500), nullable=True),
        sa.Column("alphapilot_exit_triggered_on", sa.Date(), nullable=True),
        sa.Column("alphapilot_exit_reason", sa.String(80), nullable=True),
        sa.Column("alphapilot_trigger_close", sa.Numeric(20, 4), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("actual_quantity > 0", name="ck_paper_validation_quantity_positive"),
        sa.CheckConstraint(
            "actual_entry_price > 0", name="ck_paper_validation_entry_positive"
        ),
        sa.CheckConstraint(
            "actual_exit_quantity IS NULL OR actual_exit_quantity > 0",
            name="ck_paper_validation_exit_quantity_positive",
        ),
        sa.CheckConstraint(
            "actual_exit_price IS NULL OR actual_exit_price > 0",
            name="ck_paper_validation_exit_positive",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"], ["research_positions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_validation_portfolio_created",
        "paper_validation_records",
        ["portfolio_id", "created_at"],
    )
    op.create_index(
        "ix_paper_validation_position_created",
        "paper_validation_records",
        ["position_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_validation_position_created", table_name="paper_validation_records")
    op.drop_index("ix_paper_validation_portfolio_created", table_name="paper_validation_records")
    op.drop_table("paper_validation_records")
    op.drop_column("research_reconciliation_events", "note")
    op.drop_column("research_reconciliation_events", "reason_code")
