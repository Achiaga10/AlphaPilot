from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import httpx

from alphapilot.core.config import settings
from alphapilot.market.dto import MarketCandle
from alphapilot.market.providers.base import MarketProvider


class PolygonProvider(MarketProvider):
    """Polygon.io market data provider."""

    BASE_URL = "https://api.polygon.io"

    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.BASE_URL}/v2/aggs/ticker/{ticker}/prev",
                params={"apiKey": settings.POLYGON_API_KEY},
            )
            response.raise_for_status()

            data = cast(dict[str, Any], response.json())
            return data

    async def get_history(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[MarketCandle]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 50000,
                    "apiKey": settings.POLYGON_API_KEY,
                },
            )

            response.raise_for_status()

            data = cast(dict[str, Any], response.json())

        results = data.get("results", [])

        return [
            MarketCandle(
                date=datetime.fromtimestamp(
                    item["t"] / 1000,
                ).date(),
                open=Decimal(str(item["o"])),
                high=Decimal(str(item["h"])),
                low=Decimal(str(item["l"])),
                close=Decimal(str(item["c"])),
                volume=int(item["v"]),
            )
            for item in results
        ]
