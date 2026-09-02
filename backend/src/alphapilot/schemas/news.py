from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from alphapilot.news.policy import NewsCoverage
from alphapilot.news.service import NewsRefreshScope


class NewsClassificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    classification_status: str
    classification_provider: str
    classification_model: str
    classification_version: str
    classified_at: datetime
    event_type: str | None
    impact: str | None
    severity: str | None
    confidence: Decimal | None
    reason: str | None
    failure_code: str | None


class NewsArticleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    provider: str
    provider_article_id: str | None
    canonical_url: str | None
    headline: str
    summary: str | None
    source: str | None
    image_url: str | None
    provider_category: str | None
    published_at: datetime
    received_at: datetime
    classification: NewsClassificationSchema | None = None


class NewsRefreshSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    tickers: tuple[str, ...]
    fetched: int
    inserted: int
    duplicates: int
    classified: int
    classification_failures: int
    provider_failures: tuple[str, ...]
    refreshed_at: datetime
    scope: NewsRefreshScope
    coverage: tuple[tuple[str, NewsCoverage], ...]
    aggregate_requested: tuple[str, ...]
    aggregate_returned: tuple[str, ...]
    aggregate_missing: tuple[str, ...]
    aggregate_api_calls: int
    aggregate_observations_persisted: int
    targeted_classification_attempts: int


class NewsRefreshRequestSchema(BaseModel):
    scope: NewsRefreshScope = NewsRefreshScope.OPEN_POSITIONS
    tickers: tuple[str, ...] = Field(default=(), max_length=25)
    force_aggregate: bool = False


class ExternalNewsSentimentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    provider: str
    observed_at: datetime
    provider_timestamp: datetime | None
    period_start: date
    period_end: date
    sentiment_score: Decimal
    bullish_pct: Decimal | None
    bearish_pct: Decimal | None
    mentions: int | None
    source_count: int | None
    buzz_score: Decimal | None
    trend: str | None
    request_scope: str
    evidence_strength: str
    aggregate_effect: str
    limitation: str | None
