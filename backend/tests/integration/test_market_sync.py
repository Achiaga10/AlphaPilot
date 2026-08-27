from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.dto.candle import MarketCandle
from alphapilot.market.providers.base import MarketProvider
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.market_data_ingestion import MarketDataIngestionBatchRepository
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService
from alphapilot.services.market_sync import MarketSyncService


class FakeMarketProvider(MarketProvider):
    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, object]:
        return {}

    async def get_history(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[MarketCandle]:
        return [
            MarketCandle(
                date=date(2026, 8, 1),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("99.00"),
                close=Decimal("103.00"),
                volume=100000,
            ),
            MarketCandle(
                date=date(2026, 8, 2),
                open=Decimal("103.00"),
                high=Decimal("108.00"),
                low=Decimal("102.00"),
                close=Decimal("107.00"),
                volume=120000,
            ),
        ]


@pytest.mark.asyncio
async def test_market_sync_inserts_candles(
    db_session: AsyncSession,
) -> None:
    ticker = f"T{uuid4().hex[:8].upper()}"

    company = Company(
        id=uuid4(),
        ticker=ticker,
        name="Test Company",
        exchange="NASDAQ",
        sector="Technology",
        industry="Software",
        is_active=True,
    )

    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    company_service = CompanyService(
        CompanyRepository(db_session),
    )

    candle_service = DailyCandleService(
        DailyCandleRepository(db_session),
    )

    service = MarketSyncService(
        provider=FakeMarketProvider(),
        company_service=company_service,
        candle_service=candle_service,
        ingestion_batch_service=MarketDataIngestionBatchService(
            MarketDataIngestionBatchRepository(db_session)
        ),
    )

    synced = await service.sync_company(
        ticker=ticker,
        start=date(2026, 8, 1),
        end=date(2026, 8, 2),
    )

    assert synced is True

    result = await db_session.execute(
        select(DailyCandle)
        .where(
            DailyCandle.company_id == company.id,
        )
        .order_by(DailyCandle.trading_day),
    )

    candles = list(result.scalars().all())

    assert len(candles) == 2

    assert candles[0].trading_day == date(2026, 8, 1)
    assert candles[0].open == Decimal("100.00")
    assert candles[0].high == Decimal("105.00")
    assert candles[0].low == Decimal("99.00")
    assert candles[0].close == Decimal("103.00")
    assert candles[0].volume == 100000

    assert candles[1].trading_day == date(2026, 8, 2)
    assert candles[1].open == Decimal("103.00")
    assert candles[1].high == Decimal("108.00")
    assert candles[1].low == Decimal("102.00")
    assert candles[1].close == Decimal("107.00")
    assert candles[1].volume == 120000


@pytest.mark.asyncio
async def test_market_sync_does_not_insert_current_open_session_bar(
    db_session: AsyncSession,
) -> None:
    ticker = f"T{uuid4().hex[:8].upper()}"
    company = Company(id=uuid4(), ticker=ticker, name="Test", exchange="NASDAQ", is_active=True)
    db_session.add(company)
    await db_session.commit()

    class CurrentDayProvider(FakeMarketProvider):
        async def get_history(self, ticker: str, start: date, end: date) -> list[MarketCandle]:
            del ticker, start, end
            return [
                MarketCandle(
                    date=date(2026, 8, 26),
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100.5"),
                    volume=10,
                )
            ]

    policy = CompletedDailySessionPolicy(
        now_provider=lambda: datetime(2026, 8, 26, 18, 0, tzinfo=UTC)
    )
    repository = DailyCandleRepository(db_session, policy)
    service = MarketSyncService(
        provider=CurrentDayProvider(),
        company_service=CompanyService(CompanyRepository(db_session)),
        candle_service=DailyCandleService(repository),
        ingestion_batch_service=MarketDataIngestionBatchService(
            MarketDataIngestionBatchRepository(db_session)
        ),
        session_policy=policy,
    )

    assert await service.sync_company(ticker, date(2026, 8, 26), date(2026, 8, 26)) is False
    assert await repository.get_latest(company.id) is None
