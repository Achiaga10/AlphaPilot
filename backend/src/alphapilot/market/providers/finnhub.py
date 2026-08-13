from __future__ import annotations

from datetime import date
from typing import Any

from alphapilot.market.dto import MarketCandle
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
        start: date,
        end: date,
    ) -> list[MarketCandle]:
        raise NotImplementedError
