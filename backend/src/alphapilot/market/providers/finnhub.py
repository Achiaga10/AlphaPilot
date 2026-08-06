from __future__ import annotations

from typing import Any

from alphapilot.market.providers.base import MarketProvider


class FinnhubProvider(MarketProvider):
    """Finnhub market data provider."""

    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_history(
        self,
        ticker: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError
