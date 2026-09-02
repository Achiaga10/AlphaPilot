from datetime import UTC, datetime, timedelta
from uuid import uuid4

from alphapilot.news.models import (
    ClassificationStatus,
    ClassifiedNewsEvidence,
    NewsClassificationOutput,
    NewsEventType,
    NewsImpact,
    NewsSeverity,
    SourceConfidence,
)
from alphapilot.news.policy import (
    NewsCoverage,
    NewsEffect,
    apply_news_overlay,
    assess_news,
    hard_event_confirmation,
    source_confidence,
)

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


def evidence(
    *,
    event: NewsEventType = NewsEventType.GUIDANCE,
    impact: NewsImpact = NewsImpact.NEGATIVE,
    severity: NewsSeverity = NewsSeverity.HIGH,
    confidence: float = 0.85,
    source: SourceConfidence = SourceConfidence.STANDARD,
    published_at: datetime | None = None,
    received_at: datetime | None = None,
    classified_at: datetime | None = None,
    hard_event_confirmed: bool = False,
) -> ClassifiedNewsEvidence:
    return ClassifiedNewsEvidence(
        article_id=uuid4(),
        ticker="APA",
        published_at=published_at or NOW - timedelta(hours=2),
        received_at=received_at or NOW - timedelta(hours=1),
        classified_at=classified_at or NOW - timedelta(minutes=30),
        source_confidence=source,
        status=ClassificationStatus.CLASSIFIED,
        output=NewsClassificationOutput(
            event_type=event,
            impact=impact,
            severity=severity,
            confidence=confidence,
            reason="Forward revenue expectations were reduced materially.",
        ),
        hard_event_confirmed=hard_event_confirmed,
    )


def test_high_adverse_news_blocks_buy_but_positive_news_cannot_create_buy() -> None:
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=(evidence(),), coverage=NewsCoverage.AVAILABLE
    )
    assert assessment.effect is NewsEffect.BUY_BLOCKED
    assert apply_news_overlay("BUY", assessment).final_action == "DO_NOT_BUY"

    positive = evidence(impact=NewsImpact.POSITIVE, severity=NewsSeverity.HIGH)
    no_effect = assess_news(
        ticker="APA", as_of=NOW, evidence=(positive,), coverage=NewsCoverage.AVAILABLE
    )
    overlay = apply_news_overlay("HOLD", no_effect)
    assert overlay.final_action == "HOLD"
    assert overlay.news_effect is NewsEffect.NO_EFFECT


def test_base_sell_cannot_be_cancelled_by_positive_news() -> None:
    positive = evidence(impact=NewsImpact.POSITIVE, severity=NewsSeverity.HIGH)
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=(positive,), coverage=NewsCoverage.AVAILABLE
    )
    assert apply_news_overlay("SELL", assessment).final_action == "SELL"


def test_only_narrow_severe_strong_source_event_requires_exit() -> None:
    severe = evidence(
        event=NewsEventType.BANKRUPTCY_DISTRESS,
        severity=NewsSeverity.SEVERE,
        confidence=0.95,
        source=SourceConfidence.PRIMARY,
        hard_event_confirmed=True,
    )
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=(severe,), coverage=NewsCoverage.AVAILABLE
    )
    assert assessment.effect is NewsEffect.EXIT_REQUIRED
    assert apply_news_overlay("HOLD", assessment).final_action == "EXIT_REQUIRED"

    downgrade = evidence(
        event=NewsEventType.ANALYST_RATING,
        severity=NewsSeverity.SEVERE,
        confidence=0.99,
        source=SourceConfidence.HIGH_CONFIDENCE,
    )
    ordinary = assess_news(
        ticker="APA", as_of=NOW, evidence=(downgrade,), coverage=NewsCoverage.AVAILABLE
    )
    assert ordinary.effect is NewsEffect.ATTENTION
    assert apply_news_overlay("HOLD", ordinary).final_action == "ATTENTION"


def test_unknown_or_low_confidence_cannot_create_financial_effect() -> None:
    unknown = evidence(
        event=NewsEventType.UNKNOWN,
        impact=NewsImpact.UNKNOWN,
        severity=NewsSeverity.UNKNOWN,
        confidence=0.99,
    )
    low = evidence(severity=NewsSeverity.SEVERE, confidence=0.74)
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=(unknown, low), coverage=NewsCoverage.AVAILABLE
    )
    assert assessment.effect is NewsEffect.NO_EFFECT


def test_future_published_received_or_classified_news_cannot_affect_decision() -> None:
    future_items = (
        evidence(published_at=NOW + timedelta(seconds=1)),
        evidence(received_at=NOW + timedelta(seconds=1)),
        evidence(classified_at=NOW + timedelta(seconds=1)),
    )
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=future_items, coverage=NewsCoverage.AVAILABLE
    )
    assert assessment.effect is NewsEffect.NO_EFFECT


def test_missing_coverage_fails_closed_for_buy_without_inventing_sell() -> None:
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=(), coverage=NewsCoverage.UNAVAILABLE
    )
    assert apply_news_overlay("BUY", assessment).final_action == "DO_NOT_BUY"
    assert apply_news_overlay("HOLD", assessment).final_action == "HOLD"


def test_ai_severe_and_high_confidence_alone_cannot_require_exit() -> None:
    severe = evidence(
        event=NewsEventType.BANKRUPTCY_DISTRESS,
        severity=NewsSeverity.SEVERE,
        confidence=0.99,
        source=SourceConfidence.PRIMARY,
        hard_event_confirmed=False,
    )
    assessment = assess_news(
        ticker="APA", as_of=NOW, evidence=(severe,), coverage=NewsCoverage.CURRENT
    )
    assert assessment.effect is NewsEffect.BUY_BLOCKED
    assert apply_news_overlay("HOLD", assessment).final_action == "ATTENTION"


def test_partial_and_rate_limited_coverage_fail_closed_without_sell() -> None:
    for coverage in (NewsCoverage.PARTIAL, NewsCoverage.RATE_LIMITED):
        assessment = assess_news(ticker="APA", as_of=NOW, evidence=(), coverage=coverage)
        assert assessment.effect is NewsEffect.NEWS_ASSESSMENT_PARTIAL
        assert apply_news_overlay("BUY", assessment).final_action == "DO_NOT_BUY"
        assert apply_news_overlay("HOLD", assessment).final_action == "ATTENTION"


def test_source_confidence_uses_declared_closed_rules() -> None:
    assert source_confidence("SEC") is SourceConfidence.PRIMARY
    assert source_confidence("Reuters") is SourceConfidence.HIGH_CONFIDENCE
    assert source_confidence("Local publication") is SourceConfidence.STANDARD
    assert source_confidence(None) is SourceConfidence.UNKNOWN


def test_hard_event_confirmation_requires_primary_explicit_non_rumor_fact() -> None:
    assert hard_event_confirmation(
        event_type=NewsEventType.BANKRUPTCY_DISTRESS,
        headline="Company files for Chapter 11",
        summary="A bankruptcy petition was filed today.",
        source=SourceConfidence.PRIMARY,
    )
    assert not hard_event_confirmation(
        event_type=NewsEventType.BANKRUPTCY_DISTRESS,
        headline="Rumor says company may file for Chapter 11",
        summary=None,
        source=SourceConfidence.PRIMARY,
    )
    assert not hard_event_confirmation(
        event_type=NewsEventType.BANKRUPTCY_DISTRESS,
        headline="Company files for Chapter 11",
        summary=None,
        source=SourceConfidence.HIGH_CONFIDENCE,
    )
