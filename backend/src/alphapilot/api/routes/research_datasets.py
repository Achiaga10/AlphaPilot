from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.routes.admin_data import require_admin_tools
from alphapilot.database.session import get_db
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.schemas.research_dataset import (
    ResearchDatasetCreateSchema,
    ResearchDatasetManifestSchema,
    ResearchDatasetVerificationSchema,
)
from alphapilot.services.research_dataset import (
    ResearchDatasetService,
    ResearchDatasetVerificationError,
)

router = APIRouter(prefix="/research-datasets", tags=["research-datasets"])


def get_research_dataset_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchDatasetService:
    return ResearchDatasetService(ResearchDatasetRepository(session))


@router.post(
    "",
    response_model=ResearchDatasetManifestSchema,
    dependencies=[Depends(require_admin_tools)],
)
async def create_research_dataset(
    request: ResearchDatasetCreateSchema,
    service: Annotated[ResearchDatasetService, Depends(get_research_dataset_service)],
) -> ResearchDatasetManifestSchema:
    try:
        return await service.create_snapshot(
            start=request.start,
            end=request.end,
            universe_mode=request.universe_mode,
            tickers=request.tickers,
            benchmark_ticker=request.benchmark,
            label=request.label,
            provider_expectation=request.provider_expectation,
            feed_expectation=request.feed_expectation,
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[ResearchDatasetManifestSchema])
async def list_research_datasets(
    service: Annotated[ResearchDatasetService, Depends(get_research_dataset_service)],
) -> list[ResearchDatasetManifestSchema]:
    return await service.list_manifests()


@router.get("/{snapshot_id}", response_model=ResearchDatasetManifestSchema)
async def get_research_dataset(
    snapshot_id: UUID,
    service: Annotated[ResearchDatasetService, Depends(get_research_dataset_service)],
) -> ResearchDatasetManifestSchema:
    try:
        return await service.get_manifest(snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{snapshot_id}/verify", response_model=ResearchDatasetVerificationSchema)
async def verify_research_dataset(
    snapshot_id: UUID,
    service: Annotated[ResearchDatasetService, Depends(get_research_dataset_service)],
) -> ResearchDatasetVerificationSchema:
    try:
        return await service.verify(snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResearchDatasetVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
