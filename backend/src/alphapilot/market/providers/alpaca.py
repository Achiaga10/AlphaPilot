from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import httpx

from alphapilot.core.config import settings
from alphapilot.market.dto import MarketCandle
from alphapilot.market.providers.base import MarketProvider


class AlpacaProvider(MarketProvider):
    """Market data provider backed by Alpaca Market Data API."""

    BASE_URL = "https://data.alpaca.markets"

    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        raise NotImplementedError("Alpaca quote support is not implemented yet")

    async def get_history(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[MarketCandle]:
        normalized_ticker = self._normalize_ticker(ticker)

        result = await self.get_history_many(
            tickers=[
                normalized_ticker,
            ],
            start=start,
            end=end,
        )

        return result.get(
            normalized_ticker,
            [],
        )

    async def get_history_many(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[MarketCandle]]:
        if start > end:
            raise ValueError("start must be before or equal to end")

        normalized_tickers = sorted({self._normalize_ticker(ticker) for ticker in tickers})

        if not normalized_tickers:
            raise ValueError("tickers must not be empty")

        bars_by_ticker: dict[
            str,
            list[MarketCandle],
        ] = {ticker: [] for ticker in normalized_tickers}

        page_token: str | None = None

        headers = {
            "APCA-API-KEY-ID": (settings.ALPACA_API_KEY),
            "APCA-API-SECRET-KEY": (settings.ALPACA_SECRET_KEY),
        }

        async with httpx.AsyncClient(
            timeout=60,
            headers=headers,
        ) as client:
            while True:
                params: dict[str, str | int] = {
                    "symbols": ",".join(normalized_tickers),
                    "timeframe": "1Day",
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "limit": 10000,
                    "adjustment": "split",
                    "feed": "sip",
                    "sort": "asc",
                }

                if page_token is not None:
                    params["page_token"] = page_token

                response = await client.get(
                    (f"{self.BASE_URL}/v2/stocks/bars"),
                    params=params,
                )

                response.raise_for_status()

                data = cast(
                    dict[str, Any],
                    response.json(),
                )

                response_bars = data.get(
                    "bars",
                    {},
                )

                if not isinstance(
                    response_bars,
                    dict,
                ):
                    raise RuntimeError("Invalid Alpaca bars response")

                for ticker, raw_bars in response_bars.items():
                    normalized_response_ticker = str(ticker).strip().upper()

                    if normalized_response_ticker not in bars_by_ticker:
                        continue

                    if not isinstance(
                        raw_bars,
                        list,
                    ):
                        raise RuntimeError("Invalid Alpaca ticker bars response")

                    for item in raw_bars:
                        if not isinstance(
                            item,
                            dict,
                        ):
                            continue

                        bars_by_ticker[normalized_response_ticker].append(
                            self._to_market_candle(item)
                        )

                next_page_token = data.get("next_page_token")

                if (
                    not isinstance(
                        next_page_token,
                        str,
                    )
                    or not next_page_token
                ):
                    break

                page_token = next_page_token

        for candles in bars_by_ticker.values():
            candles.sort(key=lambda candle: candle.date)

        return bars_by_ticker

    @staticmethod
    def _normalize_ticker(
        ticker: str,
    ) -> str:
        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise ValueError("ticker must not be empty")

        return normalized_ticker

    @staticmethod
    def _to_market_candle(
        item: dict[str, Any],
    ) -> MarketCandle:
        timestamp = item.get("t")

        if not isinstance(
            timestamp,
            str,
        ):
            raise RuntimeError("Alpaca bar contains no valid timestamp")

        trading_day = datetime.fromisoformat(
            timestamp.replace(
                "Z",
                "+00:00",
            )
        ).date()

        return MarketCandle(
            date=trading_day,
            open=Decimal(str(item["o"])),
            high=Decimal(str(item["h"])),
            low=Decimal(str(item["l"])),
            close=Decimal(str(item["c"])),
            volume=int(item["v"]),
        )
