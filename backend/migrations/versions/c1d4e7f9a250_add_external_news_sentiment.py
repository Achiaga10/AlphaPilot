"""Add immutable external aggregate News sentiment observations.

Revision ID: c1d4e7f9a250
Revises: a0c3e7f6b142
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d4e7f9a250"
down_revision: str | Sequence[str] | None = "a0c3e7f6b142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_news_sentiment_observations",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("sentiment_score", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("bullish_pct", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("bearish_pct", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("mentions", sa.Integer(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=True),
        sa.Column("buzz_score", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("trend", sa.String(length=30), nullable=True),
        sa.Column("request_scope", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "sentiment_score >= -1 AND sentiment_score <= 1",
            name="ck_external_news_sentiment_score",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["research_portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_news_sentiment_portfolio_ticker_observed",
        "external_news_sentiment_observations",
        ["portfolio_id", "ticker", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_news_sentiment_portfolio_ticker_observed",
        table_name="external_news_sentiment_observations",
    )
    op.drop_table("external_news_sentiment_observations")
