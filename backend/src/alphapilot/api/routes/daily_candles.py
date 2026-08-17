from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import get_db
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.schemas.daily_candle import (
    DailyCandleCreate,
    DailyCandleResponse,
)
from alphapilot.services.daily_candle import DailyCandleService

router = APIRouter(
    prefix="/daily-candles",
    tags=["daily-candles"],
)


def get_daily_candle_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DailyCandleService:
    repository = DailyCandleRepository(session)
    return DailyCandleService(repository)


@router.post(
    "",
    response_model=DailyCandleResponse,
    status_code=201,
)
async def create_daily_candle(
    data: DailyCandleCreate,
    service: Annotated[
        DailyCandleService,
        Depends(get_daily_candle_service),
    ],
) -> DailyCandleResponse:
    candle = await service.create(
        company_id=data.company_id,
        trading_day=data.trading_day,
        open_price=data.open,
        high=data.high,
        low=data.low,
        close=data.close,
        volume=data.volume,
    )

    return DailyCandleResponse.model_validate(candle)


@router.get(
    "/company/{company_id}",
    response_model=list[DailyCandleResponse],
)
async def get_daily_candle_history(
    company_id: UUID,
    start: date,
    end: date,
    service: Annotated[
        DailyCandleService,
        Depends(get_daily_candle_service),
    ],
) -> list[DailyCandleResponse]:
    candles = await service.get_history(
        company_id,
        start,
        end,
    )

    return [DailyCandleResponse.model_validate(candle) for candle in candles]
