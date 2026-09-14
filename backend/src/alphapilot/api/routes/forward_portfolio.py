from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.forward_portfolio import (
    ForwardCycleStatus,
    ForwardPortfolioStatus,
)
from alphapilot.database.session import get_db
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.schemas.forward_portfolio import (
    ForwardAnalyticsSchema,
    ForwardCycleTriggerResultSchema,
    ForwardEventSchema,
    ForwardHealthSchema,
    ForwardOrderSchema,
    ForwardPortfolioInitializeSchema,
    ForwardPortfolioMutationSchema,
    ForwardPortfolioSchema,
    ForwardPositionSchema,
    ForwardTradeSchema,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.forward_portfolio import (
    ForwardPortfolioConflictError,
    ForwardPortfolioService,
    MichoForwardDecisionProvider,
)

router = APIRouter(prefix="/forward-portfolio", tags=["Forward Portfolio"])


def get_forward_portfolio_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ForwardPortfolioService:
    orchestrator = PortfolioDecisionOrchestrator(
        CompanyService(CompanyRepository(session)),
        DailyCandleService(DailyCandleRepository(session)),
        IndexConstituentRepository(session),
    )
    return ForwardPortfolioService(session, MichoForwardDecisionProvider(orchestrator))


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Forward Portfolio not found")


@router.get("/current", response_model=ForwardPortfolioSchema | None)
async def get_current_forward_portfolio(
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardPortfolioSchema | None:
    portfolio = await service.current()
    return ForwardPortfolioSchema.model_validate(portfolio) if portfolio else None


@router.post("/initialize", response_model=ForwardPortfolioSchema, status_code=201)
async def initialize_forward_portfolio(
    request: ForwardPortfolioInitializeSchema,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardPortfolioSchema:
    try:
        portfolio = await service.initialize(
            initial_cash=request.initial_cash,
            forward_start_session=request.forward_start_session,
        )
        portfolio_id = portfolio.id
        await service.run_pending(portfolio_id)
        refreshed = await service.repo.get(portfolio_id)
        if refreshed is None:
            raise _not_found()
        return ForwardPortfolioSchema.model_validate(refreshed)
    except ForwardPortfolioConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{portfolio_id}/pause", response_model=ForwardPortfolioSchema)
async def pause_forward_portfolio(
    portfolio_id: UUID,
    request: ForwardPortfolioMutationSchema,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardPortfolioSchema:
    if not request.confirmed:
        raise HTTPException(status_code=422, detail="Explicit pause confirmation is required")
    try:
        return ForwardPortfolioSchema.model_validate(
            await service.pause(portfolio_id, expected_revision=request.expected_revision)
        )
    except ForwardPortfolioConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{portfolio_id}/resume", response_model=ForwardPortfolioSchema)
async def resume_forward_portfolio(
    portfolio_id: UUID,
    request: ForwardPortfolioMutationSchema,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardPortfolioSchema:
    if not request.confirmed:
        raise HTTPException(status_code=422, detail="Explicit resume confirmation is required")
    try:
        portfolio = await service.resume(portfolio_id, expected_revision=request.expected_revision)
        resumed_portfolio_id = portfolio.id
        await service.run_pending(resumed_portfolio_id)
        refreshed = await service.repo.get(resumed_portfolio_id)
        if refreshed is None:
            raise _not_found()
        return ForwardPortfolioSchema.model_validate(refreshed)
    except ForwardPortfolioConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{portfolio_id}/cycles/run", response_model=ForwardCycleTriggerResultSchema)
async def run_forward_cycles(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardCycleTriggerResultSchema:
    try:
        return ForwardCycleTriggerResultSchema.model_validate(
            await service.run_pending(portfolio_id), from_attributes=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{portfolio_id}/positions", response_model=list[ForwardPositionSchema])
async def list_forward_positions(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> list[ForwardPositionSchema]:
    return [
        ForwardPositionSchema.model_validate(item) for item in await service.positions(portfolio_id)
    ]


@router.get("/{portfolio_id}/orders", response_model=list[ForwardOrderSchema])
async def list_forward_orders(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> list[ForwardOrderSchema]:
    return [ForwardOrderSchema.model_validate(item) for item in await service.orders(portfolio_id)]


@router.get("/{portfolio_id}/trades", response_model=list[ForwardTradeSchema])
async def list_forward_trades(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> list[ForwardTradeSchema]:
    return [ForwardTradeSchema.model_validate(item) for item in await service.trades(portfolio_id)]


@router.get("/{portfolio_id}/events", response_model=list[ForwardEventSchema])
async def list_forward_events(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ForwardEventSchema]:
    return [
        ForwardEventSchema.model_validate(item)
        for item in await service.events(portfolio_id, limit=limit)
    ]


@router.get("/{portfolio_id}/analytics", response_model=ForwardAnalyticsSchema)
async def get_forward_analytics(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardAnalyticsSchema:
    try:
        return ForwardAnalyticsSchema.model_validate(
            await service.analytics(portfolio_id), from_attributes=True
        )
    except ValueError as exc:
        raise _not_found() from exc


@router.get("/{portfolio_id}/health", response_model=ForwardHealthSchema)
async def get_forward_health(
    portfolio_id: UUID,
    service: Annotated[ForwardPortfolioService, Depends(get_forward_portfolio_service)],
) -> ForwardHealthSchema:
    from alphapilot.core.lifespan import forward_portfolio_scheduler

    portfolio = await service.repo.get(portfolio_id)
    if portfolio is None:
        raise _not_found()
    latest = await service.repo.latest_completed_session(service.session_policy.completed_through())
    pending = (
        await service.repo.completed_sessions(
            start=portfolio.forward_start_session,
            end=latest,
            after=portfolio.last_processed_session,
        )
        if latest is not None and latest >= portfolio.forward_start_session
        else []
    )
    cycle = await service.repo.latest_cycle(portfolio.id)
    scheduler = forward_portfolio_scheduler.status
    return ForwardHealthSchema(
        scheduler_running=scheduler.scheduler_running,
        scheduler_status=scheduler.last_status,
        portfolio_status=ForwardPortfolioStatus(portfolio.status),
        last_successful_cycle=portfolio.last_successful_cycle,
        last_processed_session=portfolio.last_processed_session,
        latest_completed_market_session=latest,
        pending_sessions=len(pending),
        data_ready=latest is not None and latest >= portfolio.forward_start_session,
        last_error=portfolio.last_error or scheduler.last_error,
        latest_cycle_status=(ForwardCycleStatus(cycle.status) if cycle else None),
    )
