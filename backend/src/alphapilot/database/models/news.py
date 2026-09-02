from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class NewsArticle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("provider", "provider_article_id", name="uq_news_article_provider_id"),
        UniqueConstraint("canonical_url", name="uq_news_article_canonical_url"),
        UniqueConstraint("fingerprint", name="uq_news_article_fingerprint"),
        Index("ix_news_articles_ticker_published", "ticker", "published_at"),
    )

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_article_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NewsClassification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "news_classifications"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_news_classification_confidence",
        ),
        Index("ix_news_classifications_article_time", "article_id", "classified_at"),
    )

    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False
    )
    classification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    classification_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    classification_model: Mapped[str] = mapped_column(String(100), nullable=False)
    classification_version: Mapped[str] = mapped_column(String(100), nullable=False)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)


class NewsRefreshCoverage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "news_refresh_coverage"
    __table_args__ = (
        Index(
            "ix_news_refresh_coverage_portfolio_ticker_time",
            "portfolio_id",
            "ticker",
            "attempted_at",
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    refresh_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_succeeded: Mapped[bool] = mapped_column(nullable=False)
    articles_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    classified_articles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unclassified_articles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ExternalNewsSentimentObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_news_sentiment_observations"
    __table_args__ = (
        CheckConstraint(
            "sentiment_score >= -1 AND sentiment_score <= 1",
            name="ck_external_news_sentiment_score",
        ),
        Index(
            "ix_external_news_sentiment_portfolio_ticker_observed",
            "portfolio_id",
            "ticker",
            "observed_at",
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    bullish_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    bearish_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    mentions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buzz_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    trend: Mapped[str | None] = mapped_column(String(30), nullable=True)
    request_scope: Mapped[str] = mapped_column(String(30), nullable=False)
