from typing import Any, cast

import httpx

from alphapilot.core.config import settings
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
    ) -> list[dict[str, Any]]:
        return []
