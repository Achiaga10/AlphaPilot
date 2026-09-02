"""Add durable News Intelligence evidence.

Revision ID: d7f4a2c9e810
Revises: e23f1a2b3c4d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7f4a2c9e810"
down_revision: str | Sequence[str] | None = "e23f1a2b3c4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_article_id", sa.String(length=200), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("provider_category", sa.String(length=100), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_article_id", name="uq_news_article_provider_id"),
        sa.UniqueConstraint("canonical_url", name="uq_news_article_canonical_url"),
        sa.UniqueConstraint("fingerprint", name="uq_news_article_fingerprint"),
    )
    op.create_index(
        "ix_news_articles_ticker_published",
        "news_articles",
        ["ticker", "published_at"],
        unique=False,
    )
    op.create_table(
        "news_classifications",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("classification_status", sa.String(length=30), nullable=False),
        sa.Column("classification_provider", sa.String(length=40), nullable=False),
        sa.Column("classification_model", sa.String(length=100), nullable=False),
        sa.Column("classification_version", sa.String(length=100), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=True),
        sa.Column("impact", sa.String(length=20), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_news_classification_confidence",
        ),
        sa.ForeignKeyConstraint(["article_id"], ["news_articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id", "classification_provider", "classification_model",
            "classification_version", name="uq_news_classification_attempt_identity",
        ),
    )
    op.create_index(
        "ix_news_classifications_article_time",
        "news_classifications",
        ["article_id", "classified_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_news_classifications_article_time", table_name="news_classifications")
    op.drop_table("news_classifications")
    op.drop_index("ix_news_articles_ticker_published", table_name="news_articles")
    op.drop_table("news_articles")
