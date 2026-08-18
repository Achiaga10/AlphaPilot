from __future__ import annotations

from datetime import date
from typing import Any, cast

import httpx

from alphapilot.core.config import settings
from alphapilot.market.dto import MarketCandle
from alphapilot.market.providers.base import (
    IndexConstituentsProvider,
    MarketProvider,
)


class FinnhubProvider(
    MarketProvider,
    IndexConstituentsProvider,
):
    """Finnhub market and index data provider."""

    BASE_URL = "https://finnhub.io/api/v1"

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

    async def get_index_constituents(
        self,
        index_symbol: str,
    ) -> list[str]:
        async with httpx.AsyncClient(
            timeout=15,
        ) as client:
            response = await client.get(
                f"{self.BASE_URL}/index/constituents",
                params={
                    "symbol": index_symbol,
                    "token": settings.FINNHUB_API_KEY,
                },
            )

            response.raise_for_status()

            data = cast(
                dict[str, Any],
                response.json(),
            )

        constituents = data.get(
            "constituents",
            [],
        )

        if not isinstance(constituents, list):
            return []

        return sorted(
            {str(ticker).strip().upper() for ticker in constituents if str(ticker).strip()}
        )
