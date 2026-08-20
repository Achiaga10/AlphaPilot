from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from alphapilot.market.dto import (
    IndexConstituentData,
    MarketCandle,
)


class MarketProvider(ABC):
    """Base interface for market data providers."""

    @abstractmethod
    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        """Return current quote data."""

    @abstractmethod
    async def get_history(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[MarketCandle]:
        """Return historical market candles."""


class IndexConstituentsProvider(ABC):
    """Base interface for index constituent providers."""

    @abstractmethod
    async def get_index_constituents(
        self,
        index_symbol: str,
    ) -> list[str]:
        """Return current tickers belonging to an index."""


class IndexConstituentDetailsProvider(ABC):
    """Provides metadata for current index constituents."""

    @abstractmethod
    async def get_index_constituent_details(
        self,
        index_symbol: str,
    ) -> list[IndexConstituentData]:
        """Return current constituents with company metadata."""
