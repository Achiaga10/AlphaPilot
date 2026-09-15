from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import get_db
from alphapilot.schemas.broker_sync import (
    AlpacaSyncStatusSchema,
    BrokerAccountSchema,
    BrokerExecutionSchema,
    BrokerIgnoreRequest,
    BrokerMatchRequest,
    BrokerOrderSchema,
    BrokerPositionSchema,
    BrokerUnlinkRequest,
)
from alphapilot.services.broker_sync import (
    AlpacaBrokerSyncService,
    BrokerSyncConflictError,
    BrokerSyncNotConfiguredError,
)

router = APIRouter(prefix="/broker/alpaca", tags=["Alpaca Read Only"])


def get_broker_sync_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AlpacaBrokerSyncService:
    from alphapilot.core.lifespan import broker_sync_scheduler

    return AlpacaBrokerSyncService(
        session, scheduler_running=broker_sync_scheduler.status.scheduler_running
    )


@router.get("/status", response_model=AlpacaSyncStatusSchema)
async def status(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> AlpacaSyncStatusSchema:
    return await service.status()


@router.post("/sync", response_model=AlpacaSyncStatusSchema)
async def sync(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> AlpacaSyncStatusSchema:
    try:
        return await service.sync_now()
    except BrokerSyncNotConfiguredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/account", response_model=BrokerAccountSchema | None)
async def account(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> BrokerAccountSchema | None:
    return await service.account()


@router.get("/positions", response_model=list[BrokerPositionSchema])
async def positions(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> list[BrokerPositionSchema]:
    return await service.positions()


@router.get("/orders", response_model=list[BrokerOrderSchema])
async def orders(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BrokerOrderSchema]:
    return await service.orders(limit=limit)


@router.get("/activity", response_model=list[BrokerExecutionSchema])
async def activity(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BrokerExecutionSchema]:
    return await service.executions(limit=limit)


@router.get("/unmatched", response_model=list[BrokerExecutionSchema])
async def unmatched(
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BrokerExecutionSchema]:
    return await service.executions(unmatched_only=True, limit=limit)


@router.post("/activity/{execution_id}/manual-match", response_model=BrokerExecutionSchema)
@router.post("/activity/{execution_id}/rematch", response_model=BrokerExecutionSchema)
async def manual_match(
    execution_id: UUID,
    request: BrokerMatchRequest,
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> BrokerExecutionSchema:
    if not request.confirmed:
        raise HTTPException(status_code=422, detail="Explicit match confirmation is required")
    try:
        return await service.manual_match(
            execution_id,
            request.external_case_id,
            reason=request.reason,
            request_key=request.request_key,
        )
    except BrokerSyncConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/activity/{execution_id}/unlink", response_model=BrokerExecutionSchema)
async def unlink(
    execution_id: UUID,
    request: BrokerUnlinkRequest,
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> BrokerExecutionSchema:
    if not request.confirmed:
        raise HTTPException(status_code=422, detail="Explicit unlink confirmation is required")
    try:
        return await service.unlink(
            execution_id, reason=request.reason, request_key=request.request_key
        )
    except BrokerSyncConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/activity/{execution_id}/ignore", response_model=BrokerExecutionSchema)
async def ignore(
    execution_id: UUID,
    request: BrokerIgnoreRequest,
    service: Annotated[AlpacaBrokerSyncService, Depends(get_broker_sync_service)],
) -> BrokerExecutionSchema:
    if not request.confirmed:
        raise HTTPException(status_code=422, detail="Explicit ignore confirmation is required")
    try:
        return await service.ignore(
            execution_id, reason=request.reason, request_key=request.request_key
        )
    except BrokerSyncConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
