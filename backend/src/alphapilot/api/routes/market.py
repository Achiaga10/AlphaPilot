from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.dependencies.market import get_market_provider
from alphapilot.database.session import get_db
from alphapilot.market.providers.base import MarketProvider
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.market_data_ingestion import MarketDataIngestionBatchRepository
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService
from alphapilot.services.market_sync import MarketSyncService

router = APIRouter(
    prefix="/market",
    tags=["market"],
)


def get_market_sync_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    provider: Annotated[
        MarketProvider,
        Depends(get_market_provider),
    ],
) -> MarketSyncService:
    company_repository = CompanyRepository(session)
    candle_repository = DailyCandleRepository(session)

    company_service = CompanyService(company_repository)
    candle_service = DailyCandleService(candle_repository)

    return MarketSyncService(
        provider=provider,
        company_service=company_service,
        candle_service=candle_service,
        ingestion_batch_service=MarketDataIngestionBatchService(
            MarketDataIngestionBatchRepository(session)
        ),
    )


@router.post("/sync/{ticker}")
async def sync_market_data(
    ticker: str,
    start: date,
    end: date,
    service: Annotated[
        MarketSyncService,
        Depends(get_market_sync_service),
    ],
) -> dict[str, str]:
    synced = await service.sync_company(
        ticker=ticker,
        start=start,
        end=end,
    )

    if not synced:
        raise HTTPException(
            status_code=404,
            detail=f"Company {ticker.upper()} not found",
        )
    return {
        "status": "synced",
        "ticker": ticker.upper(),
    }
