import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.market.providers.polygon import PolygonProvider
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.scanner.scanner import Scanner
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.ema20_pullback import EMA20PullbackStrategy


@pytest.mark.asyncio
async def test_scanner_lists_only_active_sp500_companies(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(
        db_session,
    )

    candle_repository = DailyCandleRepository(
        db_session,
    )

    universe_repository = IndexConstituentRepository(
        db_session,
    )

    company_service = CompanyService(
        company_repository,
    )

    candle_service = DailyCandleService(
        candle_repository,
    )

    await company_service.create(
        Company(
            ticker="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            sector="Information Technology",
            industry="Technology Hardware",
            is_active=True,
        )
    )

    await company_service.create(
        Company(
            ticker="TSM",
            name="Taiwan Semiconductor",
            exchange="NYSE",
            sector="Information Technology",
            industry="Semiconductors",
            is_active=True,
        )
    )

    await universe_repository.sync_current(
        "^GSPC",
        [
            "AAPL",
        ],
    )

    scanner = Scanner(
        provider=PolygonProvider(),
        company_service=company_service,
        candle_service=candle_service,
        strategy=EMA20PullbackStrategy(),
        universe_repository=universe_repository,
    )

    companies = await scanner._list_scan_companies()

    tickers = [company.ticker for company in companies]

    assert tickers == [
        "AAPL",
    ]

    assert "TSM" not in tickers
