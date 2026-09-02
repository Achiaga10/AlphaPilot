from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.core.config import settings
from alphapilot.database.session import get_db
from alphapilot.market.providers.finnhub import FinnhubProvider
from alphapilot.news.classifier import (
    FallbackNewsClassifier,
    HostedNewsClassifier,
    OllamaNewsClassifier,
)
from alphapilot.news.external_sentiment import (
    AdanosNewsSentimentProvider,
    assess_external_sentiment,
)
from alphapilot.news.service import NewsService
from alphapilot.schemas.news import (
    ExternalNewsSentimentSchema,
    NewsArticleSchema,
    NewsClassificationSchema,
    NewsRefreshRequestSchema,
    NewsRefreshSchema,
)

router = APIRouter(prefix="/portfolio", tags=["news"])


def get_news_service(session: Annotated[AsyncSession, Depends(get_db)]) -> NewsService:
    fallback = OllamaNewsClassifier(settings) if settings.OLLAMA_NEWS_FALLBACK_ENABLED else None
    classifier = FallbackNewsClassifier(HostedNewsClassifier(settings), fallback)
    return NewsService(
        session,
        FinnhubProvider(),
        classifier,
        AdanosNewsSentimentProvider(settings),
        max_classification_attempts=settings.NEWS_AI_CLASSIFIER_MAX_ATTEMPTS_PER_REFRESH,
        classification_delay_seconds=settings.NEWS_AI_CLASSIFIER_DELAY_SECONDS,
        coverage_fresh_hours=settings.NEWS_COVERAGE_FRESH_HOURS,
    )


@router.post("/{portfolio_id}/news-refresh", response_model=NewsRefreshSchema)
async def refresh_portfolio_news(
    portfolio_id: UUID,
    service: Annotated[NewsService, Depends(get_news_service)],
    request: NewsRefreshRequestSchema | None = None,
) -> NewsRefreshSchema:
    payload = request or NewsRefreshRequestSchema()
    try:
        result = await service.refresh_portfolio(
            portfolio_id,
            scope=payload.scope,
            requested_tickers=payload.tickers,
            force_aggregate=payload.force_aggregate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return NewsRefreshSchema.model_validate(result, from_attributes=True)


@router.get("/{portfolio_id}/news", response_model=list[NewsArticleSchema])
async def get_portfolio_news(
    portfolio_id: UUID,
    service: Annotated[NewsService, Depends(get_news_service)],
    ticker: str | None = None,
) -> list[NewsArticleSchema]:
    records = await service.list_portfolio_news(portfolio_id, ticker=ticker)
    return [
        NewsArticleSchema(
            id=article.id,
            ticker=article.ticker,
            provider=article.provider,
            provider_article_id=article.provider_article_id,
            canonical_url=article.canonical_url,
            headline=article.headline,
            summary=article.summary,
            source=article.source,
            image_url=article.image_url,
            provider_category=article.provider_category,
            published_at=article.published_at,
            received_at=article.received_at,
            classification=(
                NewsClassificationSchema.model_validate(classification, from_attributes=True)
                if classification
                else None
            ),
        )
        for article, classification in records
    ]


@router.get(
    "/{portfolio_id}/news-sentiment",
    response_model=list[ExternalNewsSentimentSchema],
)
async def get_portfolio_news_sentiment(
    portfolio_id: UUID,
    service: Annotated[NewsService, Depends(get_news_service)],
    ticker: str | None = None,
) -> list[ExternalNewsSentimentSchema]:
    now = datetime.now(UTC)
    observations = await service.list_sentiment_observations(portfolio_id, ticker=ticker)
    output: list[ExternalNewsSentimentSchema] = []
    for item in observations:
        assessment = assess_external_sentiment(
            service.observation_snapshot(item),  # typed read model; no provider call
            as_of=now,
        )
        output.append(
            ExternalNewsSentimentSchema(
                ticker=item.ticker,
                provider=item.provider,
                observed_at=item.observed_at,
                provider_timestamp=item.provider_timestamp,
                period_start=item.period_start,
                period_end=item.period_end,
                sentiment_score=item.sentiment_score,
                bullish_pct=item.bullish_pct,
                bearish_pct=item.bearish_pct,
                mentions=item.mentions,
                source_count=item.source_count,
                buzz_score=item.buzz_score,
                trend=item.trend,
                request_scope=item.request_scope,
                evidence_strength=assessment.strength.value,
                aggregate_effect=assessment.effect.value,
                limitation=assessment.limitation,
            )
        )
    return output
