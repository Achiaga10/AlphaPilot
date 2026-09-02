"""Add per-ticker News refresh coverage provenance.

Revision ID: a0c3e7f6b142
Revises: f9b2d6e5a031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0c3e7f6b142"
down_revision: str | Sequence[str] | None = "f9b2d6e5a031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_refresh_coverage",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("refresh_scope", sa.String(length=30), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_succeeded", sa.Boolean(), nullable=False),
        sa.Column("articles_received", sa.Integer(), nullable=False),
        sa.Column("classified_articles", sa.Integer(), nullable=False),
        sa.Column("unclassified_articles", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_news_refresh_coverage_portfolio_ticker_time",
        "news_refresh_coverage",
        ["portfolio_id", "ticker", "attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_news_refresh_coverage_portfolio_ticker_time",
        table_name="news_refresh_coverage",
    )
    op.drop_table("news_refresh_coverage")
