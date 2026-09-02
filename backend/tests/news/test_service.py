from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from alphapilot.database.models.company import Company
from alphapilot.news.classifier import ClassificationAttempt
from alphapilot.news.external_sentiment import (
    ExternalNewsSentimentSnapshot,
    ExternalSentimentBatchResult,
)
from alphapilot.news.models import (
    ClassificationStatus,
    NewsClassificationOutput,
    NewsEventType,
    NewsImpact,
    NewsSeverity,
    NormalizedNewsArticle,
)
from alphapilot.news.policy import NewsCoverage, NewsEffect
from alphapilot.news.service import NewsRefreshScope, NewsService
from alphapilot.services.research_portfolio import ResearchPortfolioService


class Provider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_company_news(self, ticker, start, end):
        self.calls.append(ticker)
        now = datetime.now(UTC)
        return [
            NormalizedNewsArticle(
                ticker=ticker,
                company_name=ticker,
                provider="FINNHUB",
                provider_article_id=f"{ticker}-1",
                canonical_url=f"https://example.com/{ticker}",
                headline=f"{ticker} routine product update",
                summary="The company published a routine update.",
                source="Reuters",
                published_at=now - timedelta(hours=1),
                received_at=now,
            )
        ]


class Classifier:
    primary_identity = ("TEST", "test-model", "test-v1")

    async def classify(self, article):
        return ClassificationAttempt(
            status=ClassificationStatus.CLASSIFIED,
            provider="TEST",
            model="test-model",
            version="test-v1",
            classified_at=datetime.now(UTC),
            output=NewsClassificationOutput(
                event_type=NewsEventType.PRODUCT,
                impact=NewsImpact.NEUTRAL,
                severity=NewsSeverity.LOW,
                confidence=0.9,
                reason="Routine product information has no clear material impact.",
            ),
        )


class RateLimitedClassifier:
    primary_identity = ("TEST", "test-model", "test-v1")

    async def classify(self, article):
        return ClassificationAttempt(
            status=ClassificationStatus.RATE_LIMITED,
            provider="TEST",
            model="test-model",
            version="test-v1",
            classified_at=datetime.now(UTC),
            failure_code="HOSTED_RATE_LIMITED",
            retry_after_seconds=60,
        )


class MultiArticleProvider:
    async def get_company_news(self, ticker, start, end):
        now = datetime.now(UTC)
        return [
            NormalizedNewsArticle(
                ticker=ticker,
                company_name=ticker,
                provider="FINNHUB",
                provider_article_id=f"{ticker}-{index}",
                canonical_url=f"https://example.com/{ticker}/{index}",
                headline=f"Article {index}",
                summary="Routine update.",
                source="Reuters",
                published_at=now - timedelta(minutes=index),
                received_at=now,
            )
            for index in range(5)
        ]


class CountingClassifier(Classifier):
    def __init__(self) -> None:
        self.headlines: list[str] = []

    async def classify(self, article):
        self.headlines.append(article.headline)
        return await super().classify(article)


class AggregateProvider:
    def __init__(self, score: str = "0.4", bearish: str = "5") -> None:
        self.batches: list[tuple[str, ...]] = []
        self.score = Decimal(score)
        self.bearish = Decimal(bearish)

    async def get_sentiments(self, tickers, *, start, end):
        batch = tuple(tickers)
        self.batches.append(batch)
        now = datetime.now(UTC)
        return ExternalSentimentBatchResult(
            snapshots=tuple(
                ExternalNewsSentimentSnapshot(
                    ticker=ticker,
                    provider="ADANOS",
                    observed_at=now,
                    provider_timestamp=None,
                    period_start=start,
                    period_end=end,
                    sentiment_score=self.score,
                    bullish_pct=Decimal("70"),
                    bearish_pct=self.bearish,
                    neutral_pct=None,
                    mentions=20,
                    source_count=5,
                    buzz_score=Decimal("40"),
                    trend="stable",
                )
                for ticker in batch
            ),
            failures=(),
            request_count=1,
            elapsed_seconds=0.1,
        )

    async def get_sentiment(self, ticker, *, start, end):
        result = await self.get_sentiments((ticker,), start=start, end=end)
        return result.snapshots[0]


@pytest.mark.asyncio
async def test_candidate_refresh_is_bounded_current_and_never_expands_universe(
    db_session,
) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    provider = Provider()
    service = NewsService(
        db_session,
        provider,
        Classifier(),
        classification_delay_seconds=0,
    )

    result = await service.refresh_portfolio(
        portfolio.id,
        scope=NewsRefreshScope.CANDIDATES,
        requested_tickers=("AAA", "BBB", "AAA"),
    )

    assert result.tickers == ("AAA", "BBB")
    assert provider.calls == ["AAA", "BBB"]
    assert dict(result.coverage) == {
        "AAA": NewsCoverage.CURRENT,
        "BBB": NewsCoverage.CURRENT,
    }
    assessment = await service.assess(
        portfolio.id, "AAA", as_of=datetime.now(UTC) + timedelta(seconds=1)
    )
    assert assessment.coverage is NewsCoverage.CURRENT
    assert assessment.effect is NewsEffect.NO_EFFECT


@pytest.mark.asyncio
async def test_aggregate_refresh_batches_ten_and_targets_no_routine_articles(db_session) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    aggregate = AggregateProvider()
    classifier = CountingClassifier()
    tickers = tuple(f"T{index}" for index in range(11))
    result = await NewsService(
        db_session,
        Provider(),
        classifier,
        aggregate,
        classification_delay_seconds=0,
    ).refresh_portfolio(
        portfolio.id,
        scope=NewsRefreshScope.CANDIDATES,
        requested_tickers=tickers,
    )

    assert aggregate.batches == [tickers[:10], tickers[10:]]
    assert result.aggregate_api_calls == 2
    assert result.aggregate_observations_persisted == 11
    assert result.targeted_classification_attempts == 0
    assert classifier.headlines == []


@pytest.mark.asyncio
async def test_adverse_aggregate_targets_only_current_articles(db_session) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    aggregate = AggregateProvider(score="-0.6", bearish="80")
    classifier = CountingClassifier()
    result = await NewsService(
        db_session,
        Provider(),
        classifier,
        aggregate,
        classification_delay_seconds=0,
    ).refresh_portfolio(
        portfolio.id,
        scope=NewsRefreshScope.CANDIDATES,
        requested_tickers=("AAA",),
    )

    assert result.targeted_classification_attempts == 1
    assert classifier.headlines == ["AAA routine product update"]


@pytest.mark.asyncio
async def test_never_refreshed_and_stale_candidate_fail_closed_independently(
    db_session,
) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    service = NewsService(
        db_session,
        Provider(),
        Classifier(),
        classification_delay_seconds=0,
    )
    never = await service.assess(portfolio.id, "BBB", as_of=datetime.now(UTC))
    assert never.coverage is NewsCoverage.NEVER_REFRESHED
    assert never.effect is NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE

    await service.refresh_portfolio(
        portfolio.id,
        scope=NewsRefreshScope.CANDIDATES,
        requested_tickers=("AAA",),
    )
    stale = await service.assess(portfolio.id, "AAA", as_of=datetime.now(UTC) + timedelta(hours=25))
    untouched = await service.assess(portfolio.id, "BBB", as_of=datetime.now(UTC))
    assert stale.coverage is NewsCoverage.STALE
    assert stale.effect is NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE
    assert untouched.coverage is NewsCoverage.NEVER_REFRESHED


@pytest.mark.asyncio
async def test_candidate_scope_rejects_unbounded_or_empty_requests(db_session) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    service = NewsService(db_session, Provider(), Classifier())
    with pytest.raises(ValueError, match="requires explicit tickers"):
        await service.refresh_portfolio(
            portfolio.id,
            scope=NewsRefreshScope.CANDIDATES,
        )
    with pytest.raises(ValueError, match="limited to 25"):
        await service.refresh_portfolio(
            portfolio.id,
            scope=NewsRefreshScope.EXPLICIT_TICKERS,
            requested_tickers=tuple(f"T{index}" for index in range(26)),
        )


@pytest.mark.asyncio
async def test_rate_limited_classification_is_explicit_not_no_risk(db_session) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    service = NewsService(
        db_session,
        Provider(),
        RateLimitedClassifier(),
        classification_delay_seconds=0,
    )
    result = await service.refresh_portfolio(
        portfolio.id,
        scope=NewsRefreshScope.CANDIDATES,
        requested_tickers=("AAA",),
    )
    assert dict(result.coverage)["AAA"] is NewsCoverage.RATE_LIMITED
    assessment = await service.assess(portfolio.id, "AAA", as_of=datetime.now(UTC))
    assert assessment.coverage is NewsCoverage.RATE_LIMITED
    assert assessment.effect is NewsEffect.NEWS_ASSESSMENT_PARTIAL


@pytest.mark.asyncio
async def test_open_position_scope_remains_the_default(db_session) -> None:
    company = Company(ticker="AAA", name="AAA", exchange="NYSE", sector="Technology")
    db_session.add(company)
    await db_session.commit()
    portfolios = ResearchPortfolioService(db_session)
    portfolio = await portfolios.initialize(starting_cash=Decimal("100000"))
    await portfolios.buy(
        portfolio_id=portfolio.id,
        expected_revision=0,
        ticker="AAA",
        quantity=1,
        execution_price=Decimal("100"),
        trading_day=datetime.now(UTC).date(),
        strategy="ema20-pullback",
        profile_id="ema20-pullback-v1",
        profile_version=1,
        profile_snapshot={},
        selection_policy="relative-strength-20",
        decision="BUY",
        reason="BUY_APPROVED",
        modeled_risk_dollars=Decimal("1"),
        action_id="news-open-position-test",
    )
    provider = Provider()
    service = NewsService(
        db_session,
        provider,
        Classifier(),
        classification_delay_seconds=0,
    )
    result = await service.refresh_portfolio(portfolio.id)
    assert result.scope is NewsRefreshScope.OPEN_POSITIONS
    assert result.tickers == ("AAA",)
    assert provider.calls == ["AAA"]


@pytest.mark.asyncio
async def test_classification_batch_is_bounded_and_prioritizes_newest(db_session) -> None:
    portfolio = await ResearchPortfolioService(db_session).initialize(
        starting_cash=Decimal("100000")
    )
    classifier = CountingClassifier()
    service = NewsService(
        db_session,
        MultiArticleProvider(),
        classifier,
        max_classification_attempts=3,
        classification_delay_seconds=0,
    )
    result = await service.refresh_portfolio(
        portfolio.id,
        scope=NewsRefreshScope.CANDIDATES,
        requested_tickers=("AAA",),
    )
    assert classifier.headlines == ["Article 0", "Article 1", "Article 2"]
    assert dict(result.coverage)["AAA"] is NewsCoverage.PARTIAL
