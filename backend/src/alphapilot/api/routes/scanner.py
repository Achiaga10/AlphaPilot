from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.dependencies.market import get_market_provider
from alphapilot.database.session import get_db
from alphapilot.market.providers.base import MarketProvider
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.scanner.scanner import Scanner
from alphapilot.schemas.scanner import ScannerSignalResponse
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.ema20_pullback import EMA20PullbackStrategy

router = APIRouter(
    prefix="/scanner",
    tags=["scanner"],
)


def get_scanner(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    provider: Annotated[
        MarketProvider,
        Depends(get_market_provider),
    ],
) -> Scanner:
    company_repository = CompanyRepository(
        session,
    )

    candle_repository = DailyCandleRepository(
        session,
    )

    company_service = CompanyService(
        company_repository,
    )

    candle_service = DailyCandleService(
        candle_repository,
    )

    strategy = EMA20PullbackStrategy()

    return Scanner(
        provider=provider,
        company_service=company_service,
        candle_service=candle_service,
        strategy=strategy,
    )


@router.get(
    "/signals",
    response_model=list[ScannerSignalResponse],
)
async def scan_market(
    scanner: Annotated[
        Scanner,
        Depends(get_scanner),
    ],
) -> list[ScannerSignalResponse]:
    results = await scanner.scan_all()

    return [
        ScannerSignalResponse(
            ticker=result.ticker,
            signal=result.signal,
            price=result.price,
            ema20=result.ema20,
            ema50=result.ema50,
            market_regime=result.market_regime,
            reason=result.reason,
            generated_at=result.generated_at,
        )
        for result in results
    ]
