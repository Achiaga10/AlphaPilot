from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncService,
)


class FakeMarketSyncService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def sync_company(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> bool:
        self.calls.append(ticker)

        if ticker == "MSFT":
            return False

        if ticker == "NVDA":
            raise httpx.ConnectError("Market provider unavailable")

        return True


@pytest.mark.asyncio
async def test_market_batch_sync_continues_after_failure(
    db_session: AsyncSession,
) -> None:
    repository = IndexConstituentRepository(db_session)

    await repository.sync_current(
        "^GSPC",
        [
            "AAPL",
            "MSFT",
            "NVDA",
        ],
    )

    fake_market_sync = FakeMarketSyncService()

    service = MarketBatchSyncService(
        universe_repository=repository,
        market_sync_service=fake_market_sync,
        requests_per_minute=0,
    )

    result = await service.sync_batch(
        index_symbol="^GSPC",
        start=date(2026, 1, 1),
        end=date(2026, 8, 19),
        limit=10,
    )

    assert result.total_active == 3
    assert result.attempted == 3

    assert result.synced == 1
    assert result.skipped == 1

    assert len(result.failures) == 1

    assert result.failures[0].ticker == "NVDA"

    assert result.next_offset is None

    assert fake_market_sync.calls == [
        "AAPL",
        "MSFT",
        "NVDA",
    ]


@pytest.mark.asyncio
async def test_market_batch_sync_supports_pagination(
    db_session: AsyncSession,
) -> None:
    repository = IndexConstituentRepository(db_session)

    await repository.sync_current(
        "^GSPC",
        [
            "AAPL",
            "AMZN",
            "META",
            "MSFT",
            "NVDA",
        ],
    )

    fake_market_sync = FakeMarketSyncService()

    service = MarketBatchSyncService(
        universe_repository=repository,
        market_sync_service=fake_market_sync,
        requests_per_minute=0,
    )

    result = await service.sync_batch(
        index_symbol="^GSPC",
        start=date(2026, 1, 1),
        end=date(2026, 8, 19),
        offset=0,
        limit=2,
    )

    assert result.total_active == 5
    assert result.attempted == 2
    assert result.next_offset == 2

    assert fake_market_sync.calls == [
        "AAPL",
        "AMZN",
    ]
