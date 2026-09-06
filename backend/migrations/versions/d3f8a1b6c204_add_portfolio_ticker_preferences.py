"""Add persistent portfolio ticker recommendation preferences.

Revision ID: d3f8a1b6c204
Revises: b4e2c8a1d903
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f8a1b6c204"
down_revision: str | Sequence[str] | None = "b4e2c8a1d903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_ticker_preferences",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("recommendation_status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id", "company_id", name="uq_portfolio_ticker_preference"
        ),
    )
    op.create_index(
        "ix_portfolio_ticker_preferences_status",
        "portfolio_ticker_preferences",
        ["portfolio_id", "recommendation_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_ticker_preferences_status",
        table_name="portfolio_ticker_preferences",
    )
    op.drop_table("portfolio_ticker_preferences")
