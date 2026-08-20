from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.dependencies.universe import (
    get_index_constituent_details_provider,
    get_index_constituents_provider,
)
from alphapilot.database.session import get_db
from alphapilot.market.providers.base import (
    IndexConstituentDetailsProvider,
    IndexConstituentsProvider,
)
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.schemas.universe import (
    UniverseCompanySyncResponse,
    UniverseConstituentResponse,
    UniverseSyncResponse,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.universe import UniverseService
from alphapilot.services.universe_company_sync import (
    UniverseCompanySyncService,
)

router = APIRouter(
    prefix="/universe",
    tags=["universe"],
)


SP500_INDEX_SYMBOL = "^GSPC"


def get_universe_service(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    provider: Annotated[
        IndexConstituentsProvider,
        Depends(get_index_constituents_provider),
    ],
) -> UniverseService:
    repository = IndexConstituentRepository(
        session,
    )

    return UniverseService(
        provider=provider,
        repository=repository,
    )


def get_universe_company_sync_service(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    provider: Annotated[
        IndexConstituentDetailsProvider,
        Depends(get_index_constituent_details_provider),
    ],
) -> UniverseCompanySyncService:
    company_repository = CompanyRepository(
        session,
    )

    company_service = CompanyService(
        company_repository,
    )

    return UniverseCompanySyncService(
        provider=provider,
        company_service=company_service,
    )


@router.post(
    "/sync",
    response_model=UniverseSyncResponse,
)
async def sync_sp500_universe(
    service: Annotated[
        UniverseService,
        Depends(get_universe_service),
    ],
) -> UniverseSyncResponse:
    try:
        constituents = await service.sync_index(
            SP500_INDEX_SYMBOL,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return UniverseSyncResponse(
        status="synced",
        index_symbol=SP500_INDEX_SYMBOL,
        active_count=len(constituents),
    )


@router.post(
    "/sync-companies",
    response_model=UniverseCompanySyncResponse,
)
async def sync_sp500_companies(
    service: Annotated[
        UniverseCompanySyncService,
        Depends(get_universe_company_sync_service),
    ],
) -> UniverseCompanySyncResponse:
    try:
        created_count = await service.sync_companies(
            SP500_INDEX_SYMBOL,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return UniverseCompanySyncResponse(
        status="synced",
        index_symbol=SP500_INDEX_SYMBOL,
        created_count=created_count,
    )


@router.get(
    "/constituents",
    response_model=list[UniverseConstituentResponse],
)
async def list_sp500_constituents(
    service: Annotated[
        UniverseService,
        Depends(get_universe_service),
    ],
) -> list[UniverseConstituentResponse]:
    constituents = await service.list_active(
        SP500_INDEX_SYMBOL,
    )

    return [
        UniverseConstituentResponse(
            index_symbol=constituent.index_symbol,
            ticker=constituent.ticker,
            is_active=constituent.is_active,
        )
        for constituent in constituents
    ]
