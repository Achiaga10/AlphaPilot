import logging
from collections.abc import Awaitable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
from alphapilot.database.session import get_db
from alphapilot.schemas.copilot import (
    CopilotAnswerSchema,
    CopilotQuestionSchema,
    CopilotStatusSchema,
    UnifiedCopilotQuestionSchema,
)

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
    return CopilotOrchestrator(
        CopilotContextAssembler(session), provider, CopilotQueryResolver(session)
    )


@router.get("/status", response_model=CopilotStatusSchema)
async def status(
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> CopilotStatusSchema:
    available = settings.AI_COPILOT_ENABLED and await provider.available()
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
) -> CopilotAnswerSchema:
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
