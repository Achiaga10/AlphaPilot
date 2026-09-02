from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import httpx

from alphapilot.core.config import settings
from alphapilot.market.dto import CompanyMetadata, MarketCandle
from alphapilot.market.providers.base import (
    CompanyMetadataProvider,
    IndexConstituentsProvider,
    MarketProvider,
)
from alphapilot.news.models import NormalizedNewsArticle


class FinnhubProvider(
    MarketProvider,
    IndexConstituentsProvider,
    CompanyMetadataProvider,
):
    """Finnhub market and index data provider."""

    BASE_URL = "https://finnhub.io/api/v1"

    async def get_company_news(
        self, ticker: str, start: date, end: date
    ) -> list[NormalizedNewsArticle]:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        received_at = datetime.now(UTC)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self.BASE_URL}/company-news",
                params={
                    "symbol": normalized,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "token": settings.FINNHUB_API_KEY,
                },
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, list):
            return []
        output: list[NormalizedNewsArticle] = []
        for raw in data:
            if not isinstance(raw, dict) or not str(raw.get("headline", "")).strip():
                continue
            timestamp = raw.get("datetime")
            if not isinstance(timestamp, (int, float)):
                continue
            output.append(
                NormalizedNewsArticle(
                    ticker=normalized,
                    company_name=None,
                    provider="FINNHUB",
                    provider_article_id=(str(raw["id"]) if raw.get("id") is not None else None),
                    canonical_url=str(raw.get("url", "")).strip() or None,
                    headline=str(raw["headline"]).strip(),
                    summary=str(raw.get("summary", "")).strip() or None,
                    source=str(raw.get("source", "")).strip() or None,
                    published_at=datetime.fromtimestamp(timestamp, tz=UTC),
                    received_at=received_at,
                    image_url=str(raw.get("image", "")).strip() or None,
                    provider_category=str(raw.get("category", "")).strip() or None,
                )
            )
        return output

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

    async def get_company_metadata(self, ticker: str) -> CompanyMetadata | None:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self.BASE_URL}/stock/profile2",
                params={"symbol": normalized, "token": settings.FINNHUB_API_KEY},
            )
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
        returned_ticker = str(data.get("ticker", "")).strip().upper()
        name = str(data.get("name", "")).strip()
        raw_exchange = str(data.get("exchange", "")).strip()
        if returned_ticker != normalized or not name or not raw_exchange:
            return None
        raw_market_cap = data.get("marketCapitalization")
        market_cap = (
            Decimal(str(raw_market_cap)) * Decimal("1000000")
            if isinstance(raw_market_cap, (int, float)) and raw_market_cap > 0
            else None
        )
        industry = str(data.get("finnhubIndustry", "")).strip() or None
        return CompanyMetadata(
            ticker=normalized,
            name=name,
            exchange=self._normalize_exchange(raw_exchange),
            sector=industry,
            industry=industry,
            market_cap=market_cap,
        )

    @staticmethod
    def _normalize_exchange(value: str) -> str:
        upper = value.upper()
        if "NASDAQ" in upper:
            return "NASDAQ"
        if "NEW YORK" in upper or upper.startswith("NYSE"):
            return "NYSEARCA" if "ARCA" in upper else "NYSE"
        if "AMEX" in upper:
            return "AMEX"
        return value[:20]
