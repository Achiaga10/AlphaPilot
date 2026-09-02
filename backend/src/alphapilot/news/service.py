from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.news import (
    ExternalNewsSentimentObservation,
    NewsArticle,
    NewsClassification,
    NewsRefreshCoverage,
)
from alphapilot.database.models.research_portfolio import ResearchPosition, ResearchPositionStatus
from alphapilot.news.classifier import NewsClassifierProvider
from alphapilot.news.external_sentiment import (
    AdanosNewsSentimentProvider,
    AggregateSentimentAssessment,
    AggregateSentimentEffect,
    ExternalNewsSentimentProvider,
    ExternalNewsSentimentSnapshot,
    assess_external_sentiment,
)
from alphapilot.news.models import (
    ClassificationStatus,
    ClassifiedNewsEvidence,
    NewsClassificationOutput,
    NewsEventType,
    NewsImpact,
    NewsSeverity,
    NormalizedNewsArticle,
)
from alphapilot.news.policy import (
    NewsCoverage,
    NewsRiskAssessment,
    assess_news,
    hard_event_confirmation,
    source_confidence,
)

MAX_REFRESH_TICKERS = 25
NEWS_WINDOW_DAYS = 7
NEWS_COVERAGE_FRESH_HOURS = 24


class NewsRefreshScope(StrEnum):
    OPEN_POSITIONS = "OPEN_POSITIONS"
    CANDIDATES = "CANDIDATES"
    EXPLICIT_TICKERS = "EXPLICIT_TICKERS"


class CompanyNewsProvider(Protocol):
    async def get_company_news(
        self, ticker: str, start: date, end: date
    ) -> list[NormalizedNewsArticle]: ...


@dataclass(frozen=True)
class NewsRefreshResult:
    portfolio_id: UUID
    tickers: tuple[str, ...]
    fetched: int
    inserted: int
    duplicates: int
    classified: int
    classification_failures: int
    provider_failures: tuple[str, ...]
    refreshed_at: datetime
    scope: NewsRefreshScope = NewsRefreshScope.OPEN_POSITIONS
    coverage: tuple[tuple[str, NewsCoverage], ...] = ()
    aggregate_requested: tuple[str, ...] = ()
    aggregate_returned: tuple[str, ...] = ()
    aggregate_missing: tuple[str, ...] = ()
    aggregate_api_calls: int = 0
    aggregate_observations_persisted: int = 0
    targeted_classification_attempts: int = 0


def canonicalize_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        return None
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
        )
    )
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, "")
    )


def article_fingerprint(article: NormalizedNewsArticle) -> str:
    material = "|".join(
        (
            article.ticker.strip().upper(),
            " ".join(article.headline.lower().split()),
            (article.source or "").strip().lower(),
            article.published_at.astimezone(UTC).isoformat(),
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()


class NewsService:
    def __init__(
        self,
        session: AsyncSession,
        provider: CompanyNewsProvider,
        classifier: NewsClassifierProvider,
        sentiment_provider: ExternalNewsSentimentProvider | None = None,
        *,
        max_classification_attempts: int = 10,
        classification_delay_seconds: float = 0.25,
        coverage_fresh_hours: int = NEWS_COVERAGE_FRESH_HOURS,
    ) -> None:
        self.session = session
        self.provider = provider
        self.classifier = classifier
        self.sentiment_provider = sentiment_provider
        self.max_classification_attempts = max(0, max_classification_attempts)
        self.classification_delay_seconds = max(0.0, classification_delay_seconds)
        self.coverage_fresh_hours = max(1, coverage_fresh_hours)

    async def refresh_portfolio(
        self,
        portfolio_id: UUID,
        *,
        scope: NewsRefreshScope = NewsRefreshScope.OPEN_POSITIONS,
        requested_tickers: tuple[str, ...] = (),
        force_aggregate: bool = False,
    ) -> NewsRefreshResult:
        refreshed_at = datetime.now(UTC)
        tickers = await self._resolve_refresh_tickers(
            portfolio_id, scope=scope, requested_tickers=requested_tickers
        )
        start = refreshed_at.date() - timedelta(days=NEWS_WINDOW_DAYS - 1)
        aggregate_snapshots: dict[str, ExternalNewsSentimentSnapshot] = {}
        aggregate_requested: list[str] = []
        aggregate_returned: list[str] = []
        aggregate_missing: list[str] = []
        aggregate_api_calls = aggregate_persisted = 0
        if self.sentiment_provider is not None:
            (
                aggregate_snapshots,
                aggregate_requested,
                aggregate_returned,
                aggregate_missing,
                aggregate_api_calls,
                aggregate_persisted,
            ) = await self._refresh_aggregate_sentiment(
                portfolio_id,
                tickers,
                scope=scope,
                start=start,
                end=refreshed_at.date(),
                as_of=refreshed_at,
                force=force_aggregate,
            )
        fetched = inserted = duplicates = classified = failures = 0
        provider_failures: list[str] = []
        classification_rate_limited = False
        attempts = 0
        coverage_results: list[tuple[str, NewsCoverage]] = []
        for ticker in tickers:
            attempted_at = datetime.now(UTC)
            try:
                articles = await self.provider.get_company_news(ticker, start, refreshed_at.date())
            except Exception:  # provider failures are isolated; secrets/errors are not exposed
                provider_failures.append(ticker)
                self.session.add(
                    self._coverage_record(
                        portfolio_id=portfolio_id,
                        ticker=ticker,
                        scope=scope,
                        window_start=start,
                        window_end=refreshed_at.date(),
                        attempted_at=attempted_at,
                        status=NewsCoverage.UNAVAILABLE,
                        provider_succeeded=False,
                        failure_code="NEWS_PROVIDER_FAILED",
                    )
                )
                coverage_results.append((ticker, NewsCoverage.UNAVAILABLE))
                continue
            fetched += len(articles)
            company = await self.session.scalar(select(Company).where(Company.ticker == ticker))
            persisted: list[tuple[NewsArticle, NormalizedNewsArticle]] = []
            for normalized in articles:
                article, created = await self._persist_article(normalized, company)
                persisted.append((article, normalized))
                if not created:
                    duplicates += 1
                else:
                    inserted += 1
            pending = []
            for article, normalized in sorted(
                persisted,
                key=lambda item: (item[0].published_at, str(item[0].id)),
                reverse=True,
            ):
                if await self._has_current_classification(article.id):
                    continue
                if self.sentiment_provider is not None and not self._needs_deep_classification(
                    normalized,
                    assess_external_sentiment(aggregate_snapshots.get(ticker), as_of=refreshed_at),
                    as_of=refreshed_at,
                ):
                    continue
                pending.append((article, normalized))
            ticker_rate_limited = classification_rate_limited
            retry_after_seconds: int | None = None
            for article, normalized in pending:
                if classification_rate_limited or attempts >= self.max_classification_attempts:
                    break
                if attempts and self.classification_delay_seconds:
                    await asyncio.sleep(self.classification_delay_seconds)
                attempts += 1
                attempt = await self.classifier.classify(
                    NormalizedNewsArticle(
                        **{
                            **normalized.__dict__,
                            "company_name": company.name if company else normalized.company_name,
                        }
                    )
                )
                self.session.add(
                    NewsClassification(
                        article_id=article.id,
                        classification_status=attempt.status.value,
                        classification_provider=attempt.provider,
                        classification_model=attempt.model,
                        classification_version=attempt.version,
                        classified_at=attempt.classified_at,
                        event_type=attempt.output.event_type.value if attempt.output else None,
                        impact=attempt.output.impact.value if attempt.output else None,
                        severity=attempt.output.severity.value if attempt.output else None,
                        confidence=(
                            Decimal(str(attempt.output.confidence)) if attempt.output else None
                        ),
                        reason=attempt.output.reason if attempt.output else None,
                        failure_code=attempt.failure_code,
                    )
                )
                if attempt.output:
                    classified += 1
                else:
                    failures += 1
                if attempt.status.value == "RATE_LIMITED":
                    classification_rate_limited = True
                    ticker_rate_limited = True
                    retry_after_seconds = attempt.retry_after_seconds
            classified_count = 0
            unclassified_count = 0
            for article, _ in persisted:
                if await self._has_current_classification(article.id):
                    classified_count += 1
                else:
                    unclassified_count += 1
            if unclassified_count:
                status = (
                    NewsCoverage.RATE_LIMITED
                    if ticker_rate_limited or classification_rate_limited
                    else NewsCoverage.PARTIAL
                )
            else:
                status = NewsCoverage.CURRENT
            self.session.add(
                self._coverage_record(
                    portfolio_id=portfolio_id,
                    ticker=ticker,
                    scope=scope,
                    window_start=start,
                    window_end=refreshed_at.date(),
                    attempted_at=attempted_at,
                    status=status,
                    provider_succeeded=True,
                    articles_received=len(articles),
                    classified_articles=classified_count,
                    unclassified_articles=unclassified_count,
                    failure_code=(
                        "HOSTED_RATE_LIMITED" if status is NewsCoverage.RATE_LIMITED else None
                    ),
                    retry_after_seconds=retry_after_seconds,
                )
            )
            coverage_results.append((ticker, status))
        await self.session.commit()
        return NewsRefreshResult(
            portfolio_id=portfolio_id,
            tickers=tickers,
            fetched=fetched,
            inserted=inserted,
            duplicates=duplicates,
            classified=classified,
            classification_failures=failures,
            provider_failures=tuple(provider_failures),
            refreshed_at=refreshed_at,
            scope=scope,
            coverage=tuple(coverage_results),
            aggregate_requested=tuple(aggregate_requested),
            aggregate_returned=tuple(aggregate_returned),
            aggregate_missing=tuple(aggregate_missing),
            aggregate_api_calls=aggregate_api_calls,
            aggregate_observations_persisted=aggregate_persisted,
            targeted_classification_attempts=attempts,
        )

    async def _refresh_aggregate_sentiment(
        self,
        portfolio_id: UUID,
        tickers: tuple[str, ...],
        *,
        scope: NewsRefreshScope,
        start: date,
        end: date,
        as_of: datetime,
        force: bool,
    ) -> tuple[dict[str, ExternalNewsSentimentSnapshot], list[str], list[str], list[str], int, int]:
        snapshots: dict[str, ExternalNewsSentimentSnapshot] = {}
        to_request: list[str] = []
        for ticker in tickers:
            existing = await self.latest_sentiment_observation(portfolio_id, ticker, as_of=as_of)
            if existing is not None and not force:
                snapshot = self.observation_snapshot(existing)
                if (
                    assess_external_sentiment(snapshot, as_of=as_of).effect
                    is not AggregateSentimentEffect.UNAVAILABLE
                ):
                    snapshots[ticker] = snapshot
                    continue
            to_request.append(ticker)
        returned: list[str] = []
        missing: list[str] = []
        calls = persisted = 0
        assert self.sentiment_provider is not None
        for index in range(0, len(to_request), AdanosNewsSentimentProvider.max_batch_size):
            batch = tuple(to_request[index : index + AdanosNewsSentimentProvider.max_batch_size])
            result = await self.sentiment_provider.get_sentiments(batch, start=start, end=end)
            calls += result.request_count
            failed = {ticker for ticker, _ in result.failures}
            missing.extend(ticker for ticker in batch if ticker in failed)
            for snapshot in result.snapshots:
                company = await self.session.scalar(
                    select(Company).where(Company.ticker == snapshot.ticker)
                )
                self.session.add(
                    ExternalNewsSentimentObservation(
                        portfolio_id=portfolio_id,
                        company_id=company.id if company else None,
                        ticker=snapshot.ticker,
                        provider=snapshot.provider,
                        observed_at=snapshot.observed_at,
                        provider_timestamp=snapshot.provider_timestamp,
                        period_start=snapshot.period_start,
                        period_end=snapshot.period_end,
                        sentiment_score=snapshot.sentiment_score,
                        bullish_pct=snapshot.bullish_pct,
                        bearish_pct=snapshot.bearish_pct,
                        mentions=snapshot.mentions,
                        source_count=snapshot.source_count,
                        buzz_score=snapshot.buzz_score,
                        trend=snapshot.trend,
                        request_scope=scope.value,
                    )
                )
                snapshots[snapshot.ticker] = snapshot
                returned.append(snapshot.ticker)
                persisted += 1
        return snapshots, to_request, returned, missing, calls, persisted

    @staticmethod
    def _needs_deep_classification(
        article: NormalizedNewsArticle,
        aggregate: AggregateSentimentAssessment,
        *,
        as_of: datetime,
    ) -> bool:
        published = article.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if as_of - published > timedelta(days=NEWS_WINDOW_DAYS):
            return False
        if aggregate.effect is AggregateSentimentEffect.TARGETED_NEWS_REVIEW:
            return True
        text = f"{article.headline} {article.summary or ''}".casefold()
        return any(
            term in text
            for term in (
                "bankruptcy",
                "chapter 7",
                "chapter 11",
                "delisting",
                "trading suspension",
                "accounting fraud",
                "material misstatement",
                "authorization revoked",
                "authorization suspended",
            )
        )

    async def list_sentiment_observations(
        self, portfolio_id: UUID, *, ticker: str | None = None
    ) -> list[ExternalNewsSentimentObservation]:
        statement = select(ExternalNewsSentimentObservation).where(
            ExternalNewsSentimentObservation.portfolio_id == portfolio_id
        )
        if ticker:
            statement = statement.where(
                ExternalNewsSentimentObservation.ticker == ticker.strip().upper()
            )
        rows = await self.session.execute(
            statement.order_by(ExternalNewsSentimentObservation.observed_at.desc())
        )
        latest: dict[str, ExternalNewsSentimentObservation] = {}
        for item in rows.scalars():
            latest.setdefault(item.ticker, item)
        return [latest[key] for key in sorted(latest)]

    async def latest_sentiment_observation(
        self, portfolio_id: UUID, ticker: str, *, as_of: datetime
    ) -> ExternalNewsSentimentObservation | None:
        observation: ExternalNewsSentimentObservation | None = await self.session.scalar(
            select(ExternalNewsSentimentObservation)
            .where(
                ExternalNewsSentimentObservation.portfolio_id == portfolio_id,
                ExternalNewsSentimentObservation.ticker == ticker.strip().upper(),
                ExternalNewsSentimentObservation.observed_at <= as_of,
            )
            .order_by(ExternalNewsSentimentObservation.observed_at.desc())
            .limit(1)
        )
        return observation

    @staticmethod
    def observation_snapshot(
        observation: ExternalNewsSentimentObservation,
    ) -> ExternalNewsSentimentSnapshot:
        return ExternalNewsSentimentSnapshot(
            ticker=observation.ticker,
            provider=observation.provider,
            observed_at=observation.observed_at,
            provider_timestamp=observation.provider_timestamp,
            period_start=observation.period_start,
            period_end=observation.period_end,
            sentiment_score=observation.sentiment_score,
            bullish_pct=observation.bullish_pct,
            bearish_pct=observation.bearish_pct,
            neutral_pct=None,
            mentions=observation.mentions,
            source_count=observation.source_count,
            buzz_score=observation.buzz_score,
            trend=observation.trend,
        )

    async def _resolve_refresh_tickers(
        self,
        portfolio_id: UUID,
        *,
        scope: NewsRefreshScope,
        requested_tickers: tuple[str, ...],
    ) -> tuple[str, ...]:
        if scope is NewsRefreshScope.OPEN_POSITIONS:
            rows = await self.session.execute(
                select(ResearchPosition.ticker_at_entry)
                .where(
                    ResearchPosition.portfolio_id == portfolio_id,
                    ResearchPosition.status == ResearchPositionStatus.OPEN.value,
                )
                .order_by(ResearchPosition.ticker_at_entry)
            )
            return tuple(dict.fromkeys(str(item).upper() for item in rows.scalars()))
        tickers = tuple(
            dict.fromkeys(value.strip().upper() for value in requested_tickers if value.strip())
        )
        if not tickers:
            raise ValueError(f"{scope.value} refresh requires explicit tickers")
        if len(tickers) > MAX_REFRESH_TICKERS:
            raise ValueError(f"News refresh is limited to {MAX_REFRESH_TICKERS} tickers")
        return tickers

    @staticmethod
    def _coverage_record(
        *,
        portfolio_id: UUID,
        ticker: str,
        scope: NewsRefreshScope,
        window_start: date,
        window_end: date,
        attempted_at: datetime,
        status: NewsCoverage,
        provider_succeeded: bool,
        articles_received: int = 0,
        classified_articles: int = 0,
        unclassified_articles: int = 0,
        failure_code: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> NewsRefreshCoverage:
        return NewsRefreshCoverage(
            portfolio_id=portfolio_id,
            ticker=ticker,
            provider="FINNHUB",
            refresh_scope=scope.value,
            window_start=window_start,
            window_end=window_end,
            attempted_at=attempted_at,
            completed_at=datetime.now(UTC),
            provider_succeeded=provider_succeeded,
            articles_received=articles_received,
            classified_articles=classified_articles,
            unclassified_articles=unclassified_articles,
            status=status.value,
            failure_code=failure_code,
            retry_after_seconds=retry_after_seconds,
        )

    async def list_portfolio_news(
        self, portfolio_id: UUID, *, ticker: str | None = None
    ) -> list[tuple[NewsArticle, NewsClassification | None]]:
        position_tickers = select(ResearchPosition.ticker_at_entry).where(
            ResearchPosition.portfolio_id == portfolio_id
        )
        latest = (
            select(NewsClassification)
            .where(NewsClassification.article_id == NewsArticle.id)
            .order_by(NewsClassification.classified_at.desc())
            .limit(1)
            .correlate(NewsArticle)
        )
        if ticker:
            statement = select(NewsArticle).where(NewsArticle.ticker == ticker.strip().upper())
        else:
            statement = select(NewsArticle).where(NewsArticle.ticker.in_(position_tickers))
        articles = list(
            (
                await self.session.execute(statement.order_by(NewsArticle.published_at.desc()))
            ).scalars()
        )
        output = []
        for article in articles:
            classification = await self.session.scalar(
                latest.where(NewsClassification.article_id == article.id)
            )
            output.append((article, classification))
        return output

    async def _has_current_classification(self, article_id: UUID) -> bool:
        provider, model, version = self.classifier.primary_identity
        existing = await self.session.scalar(
            select(NewsClassification.id)
            .where(
                NewsClassification.article_id == article_id,
                NewsClassification.classification_provider == provider,
                NewsClassification.classification_model == model,
                NewsClassification.classification_version == version,
                NewsClassification.classification_status == "CLASSIFIED",
            )
            .limit(1)
        )
        return existing is not None

    async def assess(
        self, portfolio_id: UUID, ticker: str, *, as_of: datetime
    ) -> NewsRiskAssessment:
        records = await self.list_portfolio_news(portfolio_id, ticker=ticker)
        company = await self.session.scalar(
            select(Company).where(Company.ticker == ticker.strip().upper())
        )
        evidence: list[ClassifiedNewsEvidence] = []
        for article, classification in records:
            if classification is None:
                continue
            status = ClassificationStatus(classification.classification_status)
            output = None
            if status is ClassificationStatus.CLASSIFIED:
                try:
                    if classification.confidence is None:
                        raise ValueError("classified evidence requires confidence")
                    output = NewsClassificationOutput(
                        event_type=NewsEventType(str(classification.event_type)),
                        impact=NewsImpact(str(classification.impact)),
                        severity=NewsSeverity(str(classification.severity)),
                        confidence=float(classification.confidence),
                        reason=str(classification.reason),
                    )
                except (TypeError, ValueError):
                    status = ClassificationStatus.INVALID
            confidence = source_confidence(
                article.source,
                company_name=company.name if company else None,
            )
            evidence.append(
                ClassifiedNewsEvidence(
                    article_id=article.id,
                    ticker=article.ticker,
                    published_at=article.published_at,
                    received_at=article.received_at,
                    classified_at=classification.classified_at,
                    source_confidence=confidence,
                    status=status,
                    output=output,
                    hard_event_confirmed=(
                        hard_event_confirmation(
                            event_type=output.event_type,
                            headline=article.headline,
                            summary=article.summary,
                            source=confidence,
                        )
                        if output is not None
                        else False
                    ),
                )
            )
        coverage = await self.coverage_state(portfolio_id, ticker, as_of=as_of)
        return assess_news(
            ticker=ticker.upper(),
            as_of=as_of,
            evidence=tuple(evidence),
            coverage=coverage,
        )

    async def coverage_state(
        self, portfolio_id: UUID, ticker: str, *, as_of: datetime
    ) -> NewsCoverage:
        record = await self.latest_coverage_record(portfolio_id, ticker, as_of=as_of)
        if record is None:
            return NewsCoverage.NEVER_REFRESHED
        try:
            stored = NewsCoverage(record.status)
        except ValueError:
            return NewsCoverage.UNAVAILABLE
        if stored is not NewsCoverage.CURRENT:
            return stored
        completed_at = record.completed_at
        if completed_at is None:
            return NewsCoverage.UNAVAILABLE
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)
        required_start = as_of.date() - timedelta(days=NEWS_WINDOW_DAYS - 1)
        if (
            as_of - completed_at > timedelta(hours=self.coverage_fresh_hours)
            or record.window_start > required_start
            or record.window_end < as_of.date()
        ):
            return NewsCoverage.STALE
        return NewsCoverage.CURRENT

    async def latest_coverage_record(
        self, portfolio_id: UUID, ticker: str, *, as_of: datetime
    ) -> NewsRefreshCoverage | None:
        record = await self.session.scalar(
            select(NewsRefreshCoverage)
            .where(
                NewsRefreshCoverage.portfolio_id == portfolio_id,
                NewsRefreshCoverage.ticker == ticker.strip().upper(),
                NewsRefreshCoverage.attempted_at <= as_of,
            )
            .order_by(NewsRefreshCoverage.attempted_at.desc())
            .limit(1)
        )
        return record

    async def _persist_article(
        self, normalized: NormalizedNewsArticle, company: Company | None
    ) -> tuple[NewsArticle, bool]:
        canonical_url = canonicalize_url(normalized.canonical_url)
        fingerprint = article_fingerprint(normalized)
        predicates = [NewsArticle.fingerprint == fingerprint]
        if normalized.provider_article_id:
            predicates.append(
                (NewsArticle.provider == normalized.provider)
                & (NewsArticle.provider_article_id == normalized.provider_article_id)
            )
        if canonical_url:
            predicates.append(NewsArticle.canonical_url == canonical_url)
        existing = await self.session.scalar(select(NewsArticle).where(or_(*predicates)).limit(1))
        if existing:
            return existing, False
        article = NewsArticle(
            company_id=company.id if company else None,
            ticker=normalized.ticker.upper(),
            provider=normalized.provider,
            provider_article_id=normalized.provider_article_id,
            canonical_url=canonical_url,
            fingerprint=fingerprint,
            headline=normalized.headline,
            summary=normalized.summary,
            source=normalized.source,
            image_url=normalized.image_url,
            provider_category=normalized.provider_category,
            published_at=normalized.published_at,
            received_at=normalized.received_at,
        )
        self.session.add(article)
        await self.session.flush()
        return article, True
