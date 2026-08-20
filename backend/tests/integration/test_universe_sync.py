import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.market.providers.base import (
    IndexConstituentsProvider,
)
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.universe import UniverseService


class FakeIndexProvider(
    IndexConstituentsProvider,
):
    def __init__(
        self,
        tickers: list[str],
    ) -> None:
        self.tickers = tickers

    async def get_index_constituents(
        self,
        index_symbol: str,
    ) -> list[str]:
        return self.tickers


@pytest.mark.asyncio
async def test_universe_sync_updates_membership(
    db_session: AsyncSession,
) -> None:
    provider = FakeIndexProvider(
        [
            "AAPL",
            "MSFT",
            "NVDA",
        ]
    )

    repository = IndexConstituentRepository(
        db_session,
    )

    service = UniverseService(
        provider=provider,
        repository=repository,
    )

    first_sync = await service.sync_index(
        "^GSPC",
    )

    assert [item.ticker for item in first_sync] == [
        "AAPL",
        "MSFT",
        "NVDA",
    ]

    provider.tickers = [
        "MSFT",
        "NVDA",
        "AMZN",
    ]

    second_sync = await service.sync_index(
        "^GSPC",
    )

    assert [item.ticker for item in second_sync] == [
        "AMZN",
        "MSFT",
        "NVDA",
    ]

    all_constituents = await repository.list_for_index(
        "^GSPC",
    )

    by_ticker = {item.ticker: item for item in all_constituents}

    assert by_ticker["AAPL"].is_active is False
    assert by_ticker["AMZN"].is_active is True
    assert by_ticker["MSFT"].is_active is True
    assert by_ticker["NVDA"].is_active is True


@pytest.mark.asyncio
async def test_universe_sync_rejects_empty_provider_response(
    db_session: AsyncSession,
) -> None:
    provider = FakeIndexProvider(
        [
            "AAPL",
            "MSFT",
        ]
    )

    repository = IndexConstituentRepository(
        db_session,
    )

    service = UniverseService(
        provider=provider,
        repository=repository,
    )

    await service.sync_index(
        "^GSPC",
    )

    provider.tickers = []

    with pytest.raises(
        RuntimeError,
        match="Provider returned no constituents",
    ):
        await service.sync_index(
            "^GSPC",
        )

    active = await service.list_active(
        "^GSPC",
    )

    assert [item.ticker for item in active] == [
        "AAPL",
        "MSFT",
    ]
