from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.operations import (
    OperationalIncidentStatus,
    OperationalIncidentType,
    OperationalSeverity,
    OperationalSourceDomain,
)
from alphapilot.database.session import get_db
from alphapilot.schemas.operations import (
    DailyOperationsSummarySchema,
    IncidentAcknowledgeRequest,
    OperationalIncidentSchema,
    OperationsEvaluationSchema,
    OperationsHealthSchema,
)
from alphapilot.services.operations_monitor import (
    OperationsIncidentConflictError,
    OperationsIncidentNotFoundError,
    OperationsMonitor,
)

router = APIRouter(prefix="/operations", tags=["Operations"])


def _scheduler_context() -> dict[str, object]:
    from alphapilot.core.lifespan import (
        broker_sync_scheduler,
        daily_market_scheduler,
        forward_portfolio_scheduler,
        operations_monitor_scheduler,
    )

    return {
        "market_status": daily_market_scheduler.status.last_status.value,
        "market_last_completed": (
            daily_market_scheduler.status.last_successful_completed_market_session
        ),
        "forward_initialized": True,
        "forward_running": forward_portfolio_scheduler.status.scheduler_running,
        "forward_status": forward_portfolio_scheduler.status.last_status.value,
        "broker_running": broker_sync_scheduler.status.scheduler_running,
        "operations_initialized": True,
        "operations_status": operations_monitor_scheduler.status.last_status.value,
    }


def get_operations_monitor(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OperationsMonitor:
    from alphapilot.core.lifespan import operations_monitor_scheduler

    return OperationsMonitor(
        session,
        scheduler_context=_scheduler_context,
        monitor_running=operations_monitor_scheduler.status.scheduler_running,
    )


@router.get("/health", response_model=OperationsHealthSchema)
async def health(
    monitor: Annotated[OperationsMonitor, Depends(get_operations_monitor)],
) -> OperationsHealthSchema:
    return await monitor.health()


@router.get("/incidents", response_model=list[OperationalIncidentSchema])
async def incidents(
    monitor: Annotated[OperationsMonitor, Depends(get_operations_monitor)],
    status: OperationalIncidentStatus | None = None,
    severity: OperationalSeverity | None = None,
    incident_type: Annotated[OperationalIncidentType | None, Query(alias="type")] = None,
    source: OperationalSourceDomain | None = None,
) -> list[OperationalIncidentSchema]:
    return await monitor.list_incidents(
        status=status,
        severity=severity,
        incident_type=incident_type,
        source_domain=source,
    )


@router.get("/incidents/{incident_id}", response_model=OperationalIncidentSchema)
async def incident(
    incident_id: UUID,
    monitor: Annotated[OperationsMonitor, Depends(get_operations_monitor)],
) -> OperationalIncidentSchema:
    try:
        return await monitor.incident(incident_id)
    except OperationsIncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/incidents/{incident_id}/acknowledge",
    response_model=OperationalIncidentSchema,
)
async def acknowledge(
    incident_id: UUID,
    request: IncidentAcknowledgeRequest,
    monitor: Annotated[OperationsMonitor, Depends(get_operations_monitor)],
) -> OperationalIncidentSchema:
    try:
        return await monitor.acknowledge(incident_id, request.reason)
    except OperationsIncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OperationsIncidentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/daily-summary", response_model=DailyOperationsSummarySchema)
async def daily_summary(
    monitor: Annotated[OperationsMonitor, Depends(get_operations_monitor)],
) -> DailyOperationsSummarySchema:
    return await monitor.daily_summary()


@router.post("/evaluate", response_model=OperationsEvaluationSchema)
async def evaluate(
    monitor: Annotated[OperationsMonitor, Depends(get_operations_monitor)],
) -> OperationsEvaluationSchema:
    return await monitor.evaluate()
