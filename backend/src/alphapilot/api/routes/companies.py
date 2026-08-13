from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.session import get_db
from alphapilot.repositories.company import CompanyRepository
from alphapilot.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from alphapilot.services.company import CompanyService

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)


def get_company_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanyService:
    repository = CompanyRepository(session)
    return CompanyService(repository)


@router.get(
    "",
    response_model=list[CompanyResponse],
)
async def list_companies(
    service: Annotated[CompanyService, Depends(get_company_service)],
) -> list[CompanyResponse]:
    companies = await service.list_companies()

    return [CompanyResponse.model_validate(company) for company in companies]


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=201,
)
async def create_company(
    data: CompanyCreate,
    service: Annotated[CompanyService, Depends(get_company_service)],
) -> CompanyResponse:
    company = Company(
        ticker=data.ticker.upper(),
        name=data.name,
        exchange=data.exchange,
        sector=data.sector,
        industry=data.industry,
        market_cap=data.market_cap,
        is_active=data.is_active,
    )

    created_company = await service.create(company)

    return CompanyResponse.model_validate(created_company)


@router.get(
    "/{ticker}",
    response_model=CompanyResponse | None,
)
async def get_company(
    ticker: str,
    service: Annotated[CompanyService, Depends(get_company_service)],
) -> CompanyResponse | None:
    company = await service.get_company(ticker)

    if company is None:
        return None

    return CompanyResponse.model_validate(company)


@router.delete(
    "/{company_id}",
    status_code=204,
)
async def delete_company(
    company_id: UUID,
    service: Annotated[CompanyService, Depends(get_company_service)],
) -> None:
    deleted = await service.delete_company(company_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
)
async def update_company(
    company_id: UUID,
    data: CompanyUpdate,
    service: Annotated[CompanyService, Depends(get_company_service)],
) -> CompanyResponse:
    company = await service.update_company(
        company_id,
        data,
    )

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return CompanyResponse.model_validate(company)
