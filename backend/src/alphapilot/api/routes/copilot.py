import logging
import re
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.routes.news import get_news_service
from alphapilot.copilot.context import CopilotContextAssembler
from alphapilot.copilot.orchestrator import CopilotAnswer, CopilotOrchestrator
from alphapilot.copilot.provider import (
    CopilotProviderError,
    CopilotResponseInvalid,
    LLMProvider,
    OllamaProvider,
)
from alphapilot.copilot.resolution import CopilotQueryResolver
from alphapilot.core.config import settings
from alphapilot.core.lifespan import daily_market_scheduler
from alphapilot.database.session import get_db
from alphapilot.news.external_sentiment import assess_external_sentiment
from alphapilot.news.service import NewsService
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.repositories.research_data import ResearchDataRepository
from alphapilot.schemas.copilot import (
    CopilotAnswerSchema,
    CopilotFactReferenceSchema,
    CopilotQuestionSchema,
    CopilotStatusSchema,
    UnifiedCopilotQuestionSchema,
)
from alphapilot.services.admin_data import ResearchDataSummaryService
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.daily_portfolio_brief import DailyPortfolioBriefService
from alphapilot.services.position_intelligence import PositionIntelligenceService
from alphapilot.services.research_portfolio import ResearchPortfolioService

router = APIRouter(prefix="/ai/copilot", tags=["AI Copilot"])
logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    return OllamaProvider(
        settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL, settings.OLLAMA_TIMEOUT_SECONDS
    )


def get_copilot_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> CopilotOrchestrator:
    daily_brief = DailyPortfolioBriefService(
        ResearchPortfolioService(session),
        PositionIntelligenceService(session),
        PortfolioDecisionOrchestrator(
            CompanyService(CompanyRepository(session)),
            DailyCandleService(DailyCandleRepository(session)),
            IndexConstituentRepository(session),
        ),
        ResearchDataSummaryService(ResearchDataRepository(session)),
        daily_market_scheduler.status,
        get_news_service(session),
    )
    return CopilotOrchestrator(
        CopilotContextAssembler(session), provider, CopilotQueryResolver(session), daily_brief
    )


@router.get("/status", response_model=CopilotStatusSchema)
async def status(
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> CopilotStatusSchema:
    generative_enabled = settings.AI_COPILOT_ENABLED and settings.AI_GENERATIVE_EXPLANATIONS_ENABLED
    available = generative_enabled and await provider.available()
    return CopilotStatusSchema(
        enabled=settings.AI_COPILOT_ENABLED,
        provider=provider.name,
        model=provider.model or None,
        available=available,
        status=(
            "AVAILABLE"
            if available
            else "DISABLED"
            if not settings.AI_COPILOT_ENABLED
            else "DETERMINISTIC_ONLY"
            if not settings.AI_GENERATIVE_EXPLANATIONS_ENABLED
            else "AI_PROVIDER_UNAVAILABLE"
        ),
    )


async def _run(answer: Awaitable[CopilotAnswer]) -> CopilotAnswerSchema:
    try:
        return CopilotAnswerSchema.model_validate(await answer, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CopilotProviderError as exc:
        logger.warning(
            "Copilot provider unavailable: provider=%s error=%s", "ollama", type(exc).__name__
        )
        raise HTTPException(status_code=503, detail={"code": exc.code}) from exc
    except CopilotResponseInvalid as exc:
        logger.warning("Copilot response validation failed: error=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail={"code": exc.code}) from exc


@router.post(
    "/portfolio/{portfolio_id}/positions/{position_id}/ask",
    response_model=CopilotAnswerSchema,
)
async def ask_position(
    portfolio_id: UUID,
    position_id: UUID,
    request: CopilotQuestionSchema,
    orchestrator: Annotated[CopilotOrchestrator, Depends(get_copilot_orchestrator)],
) -> CopilotAnswerSchema:
    if not settings.AI_COPILOT_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "AI_COPILOT_DISABLED"})
    return await _run(orchestrator.ask_position(portfolio_id, position_id, request.question))


@router.post("/portfolio/{portfolio_id}/ask", response_model=CopilotAnswerSchema)
async def ask_portfolio(
    portfolio_id: UUID,
    request: CopilotQuestionSchema,
    orchestrator: Annotated[CopilotOrchestrator, Depends(get_copilot_orchestrator)],
) -> CopilotAnswerSchema:
    if not settings.AI_COPILOT_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "AI_COPILOT_DISABLED"})
    return await _run(orchestrator.ask_portfolio(portfolio_id, request.question))


@router.post("/general/ask", response_model=CopilotAnswerSchema)
async def ask_general(
    request: CopilotQuestionSchema,
    orchestrator: Annotated[CopilotOrchestrator, Depends(get_copilot_orchestrator)],
) -> CopilotAnswerSchema:
    if not settings.AI_COPILOT_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "AI_COPILOT_DISABLED"})
    return await _run(orchestrator.ask_general(request.question))


@router.post("/portfolio/{portfolio_id}/query", response_model=CopilotAnswerSchema)
async def ask_unified(
    portfolio_id: UUID,
    request: UnifiedCopilotQuestionSchema,
    orchestrator: Annotated[CopilotOrchestrator, Depends(get_copilot_orchestrator)],
    news: Annotated[NewsService, Depends(get_news_service)],
) -> CopilotAnswerSchema:
    if _is_news_question(request.question):
        return await _answer_news_question(portfolio_id, request, news)
    if not settings.AI_COPILOT_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "AI_COPILOT_DISABLED"})
    return await _run(
        orchestrator.ask_unified(
            portfolio_id,
            request.question,
            active_ticker=request.active_ticker,
            pending_intent=request.pending_intent,
        )
    )


def _is_news_question(question: str) -> bool:
    normalized = question.casefold()
    return any(
        word in normalized
        for word in ("news", "article", "classified", "classification", "headline")
    )


async def _answer_news_question(
    portfolio_id: UUID,
    request: UnifiedCopilotQuestionSchema,
    news: NewsService,
) -> CopilotAnswerSchema:
    records = await news.list_portfolio_news(portfolio_id)
    tickers = sorted({article.ticker for article, _ in records})
    mentioned = [
        ticker
        for ticker in tickers
        if re.search(rf"\b{re.escape(ticker)}\b", request.question, re.IGNORECASE)
    ]
    ticker = request.active_ticker.upper() if request.active_ticker else None
    if mentioned:
        ticker = mentioned[0]
    if ticker is None:
        return CopilotAnswerSchema(
            answer="Which ticker's News Intelligence do you mean?",
            scope="POSITION",
            portfolio_id=portfolio_id,
            position_id=None,
            ticker=None,
            as_of_date=None,
            grounding_status="LIMITED",
            fact_refs=(),
            limitations=("A ticker is required; no classifier call or financial action occurred.",),
            provider="alphapilot",
            model="deterministic-news-v1",
            result_status="CLARIFICATION_REQUIRED",
            intent="NEWS_INTELLIGENCE",
            resolution_status="CLARIFICATION_REQUIRED",
        )
    selected = [(article, item) for article, item in records if article.ticker == ticker]
    now = datetime.now(UTC)
    aggregate = await news.latest_sentiment_observation(portfolio_id, ticker, as_of=now)
    aggregate_assessment = assess_external_sentiment(
        news.observation_snapshot(aggregate) if aggregate else None,
        as_of=now,
    )
    coverage = await news.coverage_state(portfolio_id, ticker, as_of=now)
    coverage_record = await news.latest_coverage_record(portfolio_id, ticker, as_of=now)
    assessment = await news.assess(portfolio_id, ticker, as_of=now)
    question = request.question.casefold()
    if any(
        term in question
        for term in ("sentiment", "how many sources", "news trend", "strong or weak", "adano")
    ):
        if aggregate is None:
            answer = (
                f"No persisted Adanos aggregate News sentiment is available for {ticker}. "
                "AlphaPilot does not fabricate neutral sentiment."
            )
            aggregate_facts: tuple[CopilotFactReferenceSchema, ...] = ()
            as_of = None
        elif "cause this sell" in question or "caused this sell" in question:
            answer = (
                "No. Adanos can trigger targeted investigation but cannot directly cause "
                "SELL or EXIT_REQUIRED. Attributable evidence and deterministic hard-event "
                "confirmation are required."
            )
            aggregate_facts = ()
            as_of = aggregate.observed_at.date()
        else:
            answer = (
                f"{ticker} external News sentiment from Adanos is "
                f"{aggregate.sentiment_score}: {aggregate.bullish_pct}% bullish, "
                f"{aggregate.bearish_pct}% bearish, across {aggregate.mentions} mentions "
                f"and {aggregate.source_count} sources; trend {aggregate.trend}. Evidence is "
                f"{aggregate_assessment.strength.value}. Adanos has no direct trade authority."
            )
            aggregate_facts = (
                CopilotFactReferenceSchema(
                    fact_id="news.aggregate_sentiment",
                    source="persisted_external_news_sentiment",
                    field="sentiment",
                    label="External News Sentiment — Adanos",
                    value={
                        "score": str(aggregate.sentiment_score),
                        "bullish_pct": str(aggregate.bullish_pct),
                        "bearish_pct": str(aggregate.bearish_pct),
                        "mentions": aggregate.mentions,
                        "sources": aggregate.source_count,
                        "trend": aggregate.trend,
                        "observed_at": aggregate.observed_at.isoformat(),
                        "strength": aggregate_assessment.strength.value,
                        "effect": aggregate_assessment.effect.value,
                    },
                ),
            )
            as_of = aggregate.observed_at.date()
        return CopilotAnswerSchema(
            answer=answer,
            scope="POSITION",
            portfolio_id=portfolio_id,
            position_id=None,
            ticker=ticker,
            as_of_date=as_of,
            grounding_status="GROUNDED" if aggregate else "LIMITED",
            fact_refs=aggregate_facts,
            limitations=(
                "Adanos provider data timestamp is unavailable; observed_at is collection time.",
            ),
            provider="alphapilot",
            model="deterministic-news-v1",
            result_status="ANSWERED" if aggregate else "FACT_UNAVAILABLE",
            intent="NEWS_INTELLIGENCE",
            resolution_status="RESOLVED",
        )
    if not selected:
        if any(term in question for term in ("up to date", "last refreshed", "complete")):
            refreshed = (
                coverage_record.completed_at.isoformat()
                if coverage_record and coverage_record.completed_at
                else "never"
            )
            answer = (
                f"{ticker} News coverage is {coverage.value}. Last refresh: {refreshed}; "
                "no persisted classified article is available."
            )
        elif "ai alone" in question or "triggered by ai" in question:
            answer = (
                "No. AI classification alone cannot trigger a News SELL. "
                "Deterministic PRIMARY-source hard-event confirmation is also required."
            )
        else:
            answer = (
                f"No persisted News Intelligence article is available for {ticker}. "
                f"Coverage is {coverage.value}."
            )
        facts: tuple[CopilotFactReferenceSchema, ...] = ()
        as_of = None
    else:
        article, classification = selected[0]
        status = classification.classification_status if classification else "UNAVAILABLE"
        impact = classification.impact if classification else None
        severity = classification.severity if classification else None
        reason = classification.reason if classification else None
        provider = classification.classification_provider if classification else None
        if status == "CLASSIFIED":
            answer = (
                f"The latest {ticker} article was classified {impact} with {severity} "
                f"severity. {reason}"
            )
        else:
            answer = (
                f"The latest {ticker} article is stored, but its classification is "
                f"{status}; AlphaPilot inferred no News-driven financial action from it."
            )
        if any(term in question for term in ("up to date", "last refreshed", "complete")):
            refreshed = (
                coverage_record.completed_at.isoformat()
                if coverage_record and coverage_record.completed_at
                else "never"
            )
            counts = (
                f"{coverage_record.classified_articles} classified and "
                f"{coverage_record.unclassified_articles} unclassified"
                if coverage_record
                else "no refresh coverage record"
            )
            answer = (
                f"{ticker} News coverage is {coverage.value}. Last refresh: {refreshed}; "
                f"{counts}. Stored articles alone do not establish current coverage."
            )
        elif "ai alone" in question or "triggered by ai" in question:
            answer = (
                f"No. AI classification alone cannot trigger a News SELL. The current "
                f"News effect is {assessment.effect.value}; EXIT_REQUIRED additionally "
                "requires deterministic PRIMARY-source hard-event confirmation under "
                f"{assessment.policy_version}."
            )
        facts = (
            CopilotFactReferenceSchema(
                fact_id="news.article",
                source="persisted_news",
                field="article_id",
                label="Supporting article",
                value=str(article.id),
            ),
            CopilotFactReferenceSchema(
                fact_id="news.coverage",
                source="persisted_news_refresh",
                field="coverage",
                label="News coverage",
                value={
                    "status": coverage.value,
                    "last_refreshed": (
                        coverage_record.completed_at.isoformat()
                        if coverage_record and coverage_record.completed_at
                        else None
                    ),
                    "classified": (coverage_record.classified_articles if coverage_record else 0),
                    "unclassified": (
                        coverage_record.unclassified_articles if coverage_record else 0
                    ),
                },
            ),
            CopilotFactReferenceSchema(
                fact_id="news.headline",
                source="persisted_news",
                field="headline",
                label="Headline",
                value=article.headline,
            ),
            CopilotFactReferenceSchema(
                fact_id="news.source",
                source="persisted_news",
                field="source",
                label="Source",
                value=article.source,
            ),
            CopilotFactReferenceSchema(
                fact_id="news.classification",
                source="persisted_news",
                field="classification",
                label="AI classification",
                value={
                    "status": status,
                    "impact": impact,
                    "severity": severity,
                    "provider": provider,
                },
            ),
        )
        as_of = article.published_at.date()
    return CopilotAnswerSchema(
        answer=answer,
        scope="POSITION",
        portfolio_id=portfolio_id,
        position_id=None,
        ticker=ticker,
        as_of_date=as_of,
        grounding_status="GROUNDED" if selected else "LIMITED",
        fact_refs=facts,
        limitations=(
            "Read-only persisted News evidence; no classifier call, portfolio mutation, "
            "or broker action.",
        ),
        provider="alphapilot",
        model="deterministic-news-v1",
        result_status="ANSWERED" if selected else "FACT_UNAVAILABLE",
        intent="NEWS_INTELLIGENCE",
        resolution_status="RESOLVED",
    )
