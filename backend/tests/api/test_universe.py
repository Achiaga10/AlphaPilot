import pytest
from httpx import AsyncClient

from alphapilot.api.dependencies.universe import (
    get_index_constituent_details_provider,
    get_index_constituents_provider,
)
from alphapilot.main import app
from alphapilot.market.dto import IndexConstituentData
from alphapilot.market.providers.base import (
    IndexConstituentDetailsProvider,
    IndexConstituentsProvider,
)


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


class FakeDetailsProvider(
    IndexConstituentDetailsProvider,
):
    async def get_index_constituent_details(
        self,
        index_symbol: str,
    ) -> list[IndexConstituentData]:
        return [
            IndexConstituentData(
                ticker="AAPL",
                name="Apple Inc.",
                exchange="NASDAQ",
                sector="Information Technology",
                industry=("Technology Hardware, Storage & Peripherals"),
            ),
            IndexConstituentData(
                ticker="NVDA",
                name="Nvidia",
                exchange="NASDAQ",
                sector="Information Technology",
                industry="Semiconductors",
            ),
        ]


@pytest.mark.asyncio
async def test_sync_and_list_sp500_universe(
    client: AsyncClient,
) -> None:
    provider = FakeIndexProvider(
        [
            "NVDA",
            "AAPL",
            "MSFT",
        ]
    )

    app.dependency_overrides[get_index_constituents_provider] = lambda: provider

    try:
        sync_response = await client.post(
            "/api/v1/universe/sync",
        )

        assert sync_response.status_code == 200

        assert sync_response.json() == {
            "status": "synced",
            "index_symbol": "^GSPC",
            "active_count": 3,
        }

        list_response = await client.get(
            "/api/v1/universe/constituents",
        )

        assert list_response.status_code == 200

        data = list_response.json()

        assert [item["ticker"] for item in data] == [
            "AAPL",
            "MSFT",
            "NVDA",
        ]

    finally:
        app.dependency_overrides.pop(
            get_index_constituents_provider,
            None,
        )


@pytest.mark.asyncio
async def test_sync_sp500_companies(
    client: AsyncClient,
) -> None:
    provider = FakeDetailsProvider()

    app.dependency_overrides[get_index_constituent_details_provider] = lambda: provider

    try:
        first_response = await client.post(
            "/api/v1/universe/sync-companies",
        )

        assert first_response.status_code == 200

        assert first_response.json() == {
            "status": "synced",
            "index_symbol": "^GSPC",
            "created_count": 2,
        }

        second_response = await client.post(
            "/api/v1/universe/sync-companies",
        )

        assert second_response.status_code == 200

        assert second_response.json() == {
            "status": "synced",
            "index_symbol": "^GSPC",
            "created_count": 0,
        }

    finally:
        app.dependency_overrides.pop(
            get_index_constituent_details_provider,
            None,
        )
