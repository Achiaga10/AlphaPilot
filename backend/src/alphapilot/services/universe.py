from alphapilot.database.models.index_constituent import (
    IndexConstituent,
)
from alphapilot.market.providers.base import (
    IndexConstituentsProvider,
)
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)


class UniverseService:
    """Synchronizes index membership from an external provider."""

    def __init__(
        self,
        provider: IndexConstituentsProvider,
        repository: IndexConstituentRepository,
    ) -> None:
        self.provider = provider
        self.repository = repository

    async def sync_index(
        self,
        index_symbol: str,
    ) -> list[IndexConstituent]:
        tickers = await self.provider.get_index_constituents(
            index_symbol,
        )

        if not tickers:
            raise RuntimeError(f"Provider returned no constituents for {index_symbol}")

        return await self.repository.sync_current(
            index_symbol=index_symbol,
            tickers=tickers,
        )

    async def list_active(
        self,
        index_symbol: str,
    ) -> list[IndexConstituent]:
        return await self.repository.list_active(
            index_symbol,
        )
