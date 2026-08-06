from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import get_db
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService


def get_company_service(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CompanyService:
    repository = CompanyRepository(session)
    return CompanyService(repository)


def get_daily_candle_service(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> DailyCandleService:
    repository = DailyCandleRepository(session)
    return DailyCandleService(repository)
