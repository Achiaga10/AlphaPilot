from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from alphapilot.news.models import (
    ClassificationStatus,
    ClassifiedNewsEvidence,
    NewsEventType,
    NewsImpact,
    NewsSeverity,
    SourceConfidence,
)

POLICY_VERSION = "news-decision-overlay-v1"
MIN_CONFIDENCE = 0.75
EXIT_MIN_CONFIDENCE = 0.90
ASSESSMENT_WINDOW = timedelta(days=7)
EXIT_WINDOW = timedelta(hours=72)


class NewsCoverage(StrEnum):
    CURRENT = "CURRENT"
    AVAILABLE = "CURRENT"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    NEVER_REFRESHED = "NEVER_REFRESHED"


class NewsEffect(StrEnum):
    NO_EFFECT = "NO_EFFECT"
    ATTENTION = "ATTENTION"
    BUY_BLOCKED = "BUY_BLOCKED"
    EXIT_REQUIRED = "EXIT_REQUIRED"
    NEWS_ASSESSMENT_PARTIAL = "NEWS_ASSESSMENT_PARTIAL"
    NEWS_ASSESSMENT_UNAVAILABLE = "NEWS_ASSESSMENT_UNAVAILABLE"


@dataclass(frozen=True)
class NewsRiskAssessment:
    ticker: str
    as_of: datetime
    coverage: NewsCoverage
    effect: NewsEffect
    reason: str
    supporting_article_ids: tuple[UUID, ...] = ()
    policy_version: str = POLICY_VERSION


@dataclass(frozen=True)
class NewsDecisionOverlay:
    base_action: str
    news_effect: NewsEffect
    final_action: str
    reason: str
    policy_version: str
    supporting_article_ids: tuple[UUID, ...]


_BUY_EXCLUDED = {
    NewsEventType.ANALYST_RATING,
    NewsEventType.MACRO_SECTOR,
    NewsEventType.OTHER,
    NewsEventType.UNKNOWN,
}
_EXIT_EVENTS = {
    NewsEventType.BANKRUPTCY_DISTRESS,
    NewsEventType.DELISTING,
    NewsEventType.TRADING_HALT,
    NewsEventType.ACCOUNTING,
    NewsEventType.LEGAL_REGULATORY,
}

_HIGH_CONFIDENCE_SOURCES = {
    "reuters",
    "associated press",
    "bloomberg",
    "dow jones",
    "the wall street journal",
    "wall street journal",
}

_UNCERTAIN_HARD_EVENT_TERMS = (
    "rumor",
    "rumour",
    "may file",
    "might file",
    "could file",
    "considering",
    "possible delisting",
    "at risk of delisting",
    "going concern",
    "investigation",
    "inquiry",
)

_HARD_EVENT_TERMS: dict[NewsEventType, tuple[str, ...]] = {
    NewsEventType.BANKRUPTCY_DISTRESS: (
        "filed for chapter 7",
        "filed for chapter 11",
        "files for chapter 7",
        "files for chapter 11",
        "bankruptcy petition filed",
    ),
    NewsEventType.DELISTING: (
        "notice of delisting",
        "will be delisted",
        "exchange ordered delisting",
    ),
    NewsEventType.TRADING_HALT: (
        "trading suspended by",
        "exchange suspended trading",
        "regulator suspended trading",
    ),
    NewsEventType.ACCOUNTING: (
        "charged with accounting fraud",
        "accounting fraud finding",
        "material financial misstatement",
        "fraudulent financial statements",
    ),
    NewsEventType.LEGAL_REGULATORY: (
        "license revoked",
        "authorization revoked",
        "regulator ordered operations suspended",
        "ordered to cease operations",
    ),
}


def source_confidence(source: str | None, *, company_name: str | None = None) -> SourceConfidence:
    normalized = " ".join((source or "").lower().split())
    if not normalized:
        return SourceConfidence.UNKNOWN
    if normalized in {"sec", "u.s. securities and exchange commission"}:
        return SourceConfidence.PRIMARY
    if company_name and normalized in {
        company_name.strip().lower(),
        f"{company_name.strip().lower()} investor relations",
    }:
        return SourceConfidence.PRIMARY
    if normalized in _HIGH_CONFIDENCE_SOURCES:
        return SourceConfidence.HIGH_CONFIDENCE
    return SourceConfidence.STANDARD


def hard_event_confirmation(
    *,
    event_type: NewsEventType,
    headline: str,
    summary: str | None,
    source: SourceConfidence,
) -> bool:
    """Confirm a closed hard-event fact independently of the AI label."""
    if source is not SourceConfidence.PRIMARY or event_type not in _HARD_EVENT_TERMS:
        return False
    text = " ".join(f"{headline} {summary or ''}".lower().split())
    if any(term in text for term in _UNCERTAIN_HARD_EVENT_TERMS):
        return False
    return any(term in text for term in _HARD_EVENT_TERMS[event_type])


def assess_news(
    *,
    ticker: str,
    as_of: datetime,
    evidence: tuple[ClassifiedNewsEvidence, ...],
    coverage: NewsCoverage,
) -> NewsRiskAssessment:
    if coverage is not NewsCoverage.CURRENT:
        partial = coverage in {NewsCoverage.PARTIAL, NewsCoverage.RATE_LIMITED}
        return NewsRiskAssessment(
            ticker=ticker,
            as_of=as_of,
            coverage=coverage,
            effect=(
                NewsEffect.NEWS_ASSESSMENT_PARTIAL
                if partial
                else NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE
            ),
            reason=f"News assessment coverage is {coverage.value}",
        )
    usable = [item for item in evidence if _usable(item, as_of)]
    exits = [item for item in usable if _exit_evidence(item, as_of)]
    if exits:
        strongest = _strongest(exits)
        return _assessment(strongest, ticker, as_of, NewsEffect.EXIT_REQUIRED)
    blocked = [item for item in usable if _buy_block_evidence(item)]
    if blocked:
        strongest = _strongest(blocked)
        return _assessment(strongest, ticker, as_of, NewsEffect.BUY_BLOCKED)
    attention = [item for item in usable if _attention_evidence(item)]
    if attention:
        strongest = _strongest(attention)
        return _assessment(strongest, ticker, as_of, NewsEffect.ATTENTION)
    return NewsRiskAssessment(
        ticker=ticker,
        as_of=as_of,
        coverage=coverage,
        effect=NewsEffect.NO_EFFECT,
        reason="No qualifying adverse News evidence",
    )


def apply_news_overlay(base_action: str, assessment: NewsRiskAssessment) -> NewsDecisionOverlay:
    base = base_action.upper()
    effect = assessment.effect
    if base == "SELL":
        final = "SELL"
        reason = "Base technical SELL remains authoritative"
    elif effect is NewsEffect.EXIT_REQUIRED and base in {"HOLD", "ATTENTION"}:
        final = "EXIT_REQUIRED"
        reason = assessment.reason
    elif base == "BUY" and effect in {
        NewsEffect.BUY_BLOCKED,
        NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
        NewsEffect.NEWS_ASSESSMENT_PARTIAL,
        NewsEffect.EXIT_REQUIRED,
    }:
        final = "DO_NOT_BUY"
        reason = assessment.reason
    elif base == "BUY":
        final = "BUY"
        reason = "Technical BUY remains eligible after News overlay"
    elif (
        effect
        in {
            NewsEffect.ATTENTION,
            NewsEffect.BUY_BLOCKED,
            NewsEffect.NEWS_ASSESSMENT_PARTIAL,
        }
        and base == "HOLD"
    ):
        final = "ATTENTION"
        reason = assessment.reason
    else:
        final = base
        reason = "News cannot promote the base technical action"
    return NewsDecisionOverlay(
        base_action=base,
        news_effect=effect,
        final_action=final,
        reason=reason,
        policy_version=assessment.policy_version,
        supporting_article_ids=assessment.supporting_article_ids,
    )


def _usable(item: ClassifiedNewsEvidence, as_of: datetime) -> bool:
    output = item.output
    return bool(
        item.status is ClassificationStatus.CLASSIFIED
        and output is not None
        and item.published_at <= as_of
        and item.received_at <= as_of
        and item.classified_at <= as_of
        and as_of - item.published_at <= ASSESSMENT_WINDOW
        and output.confidence >= MIN_CONFIDENCE
        and item.source_confidence is not SourceConfidence.UNKNOWN
    )


def _buy_block_evidence(item: ClassifiedNewsEvidence) -> bool:
    assert item.output is not None
    return (
        item.output.impact is NewsImpact.NEGATIVE
        and item.output.severity in {NewsSeverity.HIGH, NewsSeverity.SEVERE}
        and item.output.event_type not in _BUY_EXCLUDED
    )


def _attention_evidence(item: ClassifiedNewsEvidence) -> bool:
    assert item.output is not None
    return item.output.impact in {
        NewsImpact.NEGATIVE,
        NewsImpact.MIXED,
    } and item.output.severity in {NewsSeverity.MEDIUM, NewsSeverity.HIGH, NewsSeverity.SEVERE}


def _exit_evidence(item: ClassifiedNewsEvidence, as_of: datetime) -> bool:
    assert item.output is not None
    return (
        item.output.impact is NewsImpact.NEGATIVE
        and item.output.severity is NewsSeverity.SEVERE
        and item.output.confidence >= EXIT_MIN_CONFIDENCE
        and item.output.event_type in _EXIT_EVENTS
        and item.source_confidence in {SourceConfidence.PRIMARY, SourceConfidence.HIGH_CONFIDENCE}
        and as_of - item.published_at <= EXIT_WINDOW
        and item.hard_event_confirmed
    )


def _strongest(items: list[ClassifiedNewsEvidence]) -> ClassifiedNewsEvidence:
    order = {
        NewsSeverity.LOW: 0,
        NewsSeverity.MEDIUM: 1,
        NewsSeverity.HIGH: 2,
        NewsSeverity.SEVERE: 3,
        NewsSeverity.UNKNOWN: -1,
    }

    def key(item: ClassifiedNewsEvidence) -> tuple[int, float, datetime, str]:
        assert item.output is not None
        return (
            order[item.output.severity],
            item.output.confidence,
            item.published_at,
            str(item.article_id),
        )

    return max(items, key=key)


def _assessment(
    evidence: ClassifiedNewsEvidence,
    ticker: str,
    as_of: datetime,
    effect: NewsEffect,
) -> NewsRiskAssessment:
    assert evidence.output is not None
    return NewsRiskAssessment(
        ticker=ticker,
        as_of=as_of,
        coverage=NewsCoverage.CURRENT,
        effect=effect,
        reason=evidence.output.reason,
        supporting_article_ids=(evidence.article_id,),
    )
