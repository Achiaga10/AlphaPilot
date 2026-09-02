from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NewsEventType(StrEnum):
    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    M_AND_A = "M_AND_A"
    ANALYST_RATING = "ANALYST_RATING"
    MANAGEMENT = "MANAGEMENT"
    LEGAL_REGULATORY = "LEGAL_REGULATORY"
    ACCOUNTING = "ACCOUNTING"
    CAPITAL_RAISE = "CAPITAL_RAISE"
    BUYBACK_DIVIDEND = "BUYBACK_DIVIDEND"
    PRODUCT = "PRODUCT"
    CUSTOMER_CONTRACT = "CUSTOMER_CONTRACT"
    SEC_FILING = "SEC_FILING"
    BANKRUPTCY_DISTRESS = "BANKRUPTCY_DISTRESS"
    DELISTING = "DELISTING"
    TRADING_HALT = "TRADING_HALT"
    CYBERSECURITY = "CYBERSECURITY"
    LAYOFFS_COST_REDUCTION = "LAYOFFS_COST_REDUCTION"
    MACRO_SECTOR = "MACRO_SECTOR"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class NewsImpact(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class NewsSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class ClassificationStatus(StrEnum):
    CLASSIFIED = "CLASSIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID = "INVALID"


class SourceConfidence(StrEnum):
    PRIMARY = "PRIMARY"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    STANDARD = "STANDARD"
    UNKNOWN = "UNKNOWN"


class NewsClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: NewsEventType
    impact: NewsImpact
    severity: NewsSeverity
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True)
class NormalizedNewsArticle:
    ticker: str
    company_name: str | None
    provider: str
    provider_article_id: str | None
    canonical_url: str | None
    headline: str
    summary: str | None
    source: str | None
    published_at: datetime
    received_at: datetime
    image_url: str | None = None
    provider_category: str | None = None


@dataclass(frozen=True)
class ClassifiedNewsEvidence:
    article_id: UUID
    ticker: str
    published_at: datetime
    received_at: datetime
    classified_at: datetime
    source_confidence: SourceConfidence
    status: ClassificationStatus
    output: NewsClassificationOutput | None
    hard_event_confirmed: bool = False
