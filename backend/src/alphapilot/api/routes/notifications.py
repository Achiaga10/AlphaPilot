"""Operational notification status, history, preferences, and durable actions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import get_db
from alphapilot.schemas.notifications import (
    NotificationPreferenceSchema,
    NotificationPreferenceUpdate,
    NotificationSchema,
    NotificationStatusSchema,
    NotificationTestRequest,
)
from alphapilot.services.notifications import (
    NotificationConfigurationError,
    NotificationConflictError,
    NotificationNotFoundError,
    NotificationService,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationService:
    from alphapilot.core.lifespan import notification_scheduler

    return NotificationService(
        session,
        worker_running=notification_scheduler.status.scheduler_running,
    )


@router.get("/status", response_model=NotificationStatusSchema)
async def notification_status(
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationStatusSchema:
    return await service.status()


@router.get("", response_model=list[NotificationSchema])
async def notifications(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[NotificationSchema]:
    return await service.list_notifications(limit=limit)


@router.get("/preferences", response_model=NotificationPreferenceSchema)
async def preferences(
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationPreferenceSchema:
    return await service.preference()


@router.put("/preferences", response_model=NotificationPreferenceSchema)
async def update_preferences(
    request: NotificationPreferenceUpdate,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationPreferenceSchema:
    return await service.update_preference(request)


@router.post("/test", response_model=NotificationSchema, status_code=status.HTTP_201_CREATED)
async def test_notification(
    request: NotificationTestRequest,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationSchema:
    try:
        return await service.create_test(request.recipient)
    except NotificationConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{notification_id}/retry", response_model=NotificationSchema)
async def retry_notification(
    notification_id: UUID,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationSchema:
    try:
        return await service.retry(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotificationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{notification_id}", response_model=NotificationSchema)
async def notification(
    notification_id: UUID,
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationSchema:
    try:
        return await service.notification(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
