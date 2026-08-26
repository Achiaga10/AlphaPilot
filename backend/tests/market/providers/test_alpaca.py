from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from alphapilot.core.config import settings
from alphapilot.market.providers.alpaca import (
    AlpacaProvider,
)
from alphapilot.market.providers.errors import MarketDataFeedNotAuthorizedError


@pytest.mark.asyncio
async def test_alpaca_get_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "bars": {
            "AAPL": [
                {
                    "t": "2026-08-17T04:00:00Z",
                    "o": 225.10,
                    "h": 228.20,
                    "l": 224.50,
                    "c": 227.75,
                    "v": 50123456,
                    "n": 500000,
                    "vw": 226.91,
                },
                {
                    "t": "2026-08-18T04:00:00Z",
                    "o": 227.90,
                    "h": 230.00,
                    "l": 226.80,
                    "c": 229.40,
                    "v": 48765432,
                    "n": 490000,
                    "vw": 228.75,
                },
            ]
        },
        "next_page_token": None,
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"

        assert request.url.path == "/v2/stocks/bars"

        assert request.headers["APCA-API-KEY-ID"] == "test-api-key"

        assert request.headers["APCA-API-SECRET-KEY"] == "test-secret-key"

        assert request.url.params["symbols"] == "AAPL"

        assert request.url.params["timeframe"] == "1Day"

        assert request.url.params["adjustment"] == "split"

        assert request.url.params["feed"] == "sip"

        assert request.url.params["start"] == "2026-08-17"

        assert request.url.params["end"] == "2026-08-18"

        return httpx.Response(
            status_code=200,
            json=payload,
        )

    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient

    def create_client(
        *args: Any,
        **kwargs: Any,
    ) -> httpx.AsyncClient:
        kwargs["transport"] = transport

        return original_async_client(
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        settings,
        "ALPACA_API_KEY",
        "test-api-key",
    )

    monkeypatch.setattr(
        settings,
        "ALPACA_SECRET_KEY",
        "test-secret-key",
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        create_client,
    )

    provider = AlpacaProvider("sip")

    candles = await provider.get_history(
        ticker="AAPL",
        start=date(2026, 8, 17),
        end=date(2026, 8, 18),
    )

    assert len(candles) == 2

    first = candles[0]

    assert first.date == date(
        2026,
        8,
        17,
    )

    assert first.open == Decimal("225.1")

    assert first.high == Decimal("228.2")

    assert first.low == Decimal("224.5")

    assert first.close == Decimal("227.75")

    assert first.volume == 50123456

    second = candles[1]

    assert second.date == date(
        2026,
        8,
        18,
    )

    assert second.close == Decimal("229.4")


@pytest.mark.asyncio
async def test_alpaca_get_history_normalizes_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.params["symbols"] == "AAPL"

        return httpx.Response(
            status_code=200,
            json={
                "bars": {
                    "AAPL": [],
                },
                "next_page_token": None,
            },
        )

    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient

    def create_client(
        *args: Any,
        **kwargs: Any,
    ) -> httpx.AsyncClient:
        kwargs["transport"] = transport

        return original_async_client(
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        create_client,
    )

    provider = AlpacaProvider()

    candles = await provider.get_history(
        ticker="  aapl  ",
        start=date(2026, 8, 17),
        end=date(2026, 8, 18),
    )

    assert candles == []


@pytest.mark.asyncio
async def test_alpaca_get_history_rejects_invalid_range() -> None:
    provider = AlpacaProvider()

    with pytest.raises(
        ValueError,
        match=("start must be before or equal to end"),
    ):
        await provider.get_history(
            ticker="AAPL",
            start=date(2026, 8, 18),
            end=date(2026, 8, 17),
        )


@pytest.mark.asyncio
async def test_alpaca_get_history_many_with_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    first_payload = {
        "bars": {
            "AAPL": [
                {
                    "t": "2026-08-17T04:00:00Z",
                    "o": 305.0,
                    "h": 308.0,
                    "l": 302.0,
                    "c": 305.59,
                    "v": 38000000,
                }
            ],
            "MSFT": [
                {
                    "t": "2026-08-17T04:00:00Z",
                    "o": 500.0,
                    "h": 505.0,
                    "l": 498.0,
                    "c": 503.0,
                    "v": 20000000,
                }
            ],
        },
        "next_page_token": "page-2",
    }

    second_payload = {
        "bars": {
            "AAPL": [
                {
                    "t": "2026-08-18T04:00:00Z",
                    "o": 307.58,
                    "h": 311.49,
                    "l": 305.74,
                    "c": 310.03,
                    "v": 53629117,
                }
            ],
            "MSFT": [
                {
                    "t": "2026-08-18T04:00:00Z",
                    "o": 504.0,
                    "h": 510.0,
                    "l": 502.0,
                    "c": 508.0,
                    "v": 21000000,
                }
            ],
        },
        "next_page_token": None,
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(request)

        assert request.url.params["symbols"] == "AAPL,MSFT"

        if len(requests) == 1:
            assert "page_token" not in request.url.params

            return httpx.Response(
                status_code=200,
                json=first_payload,
            )

        assert request.url.params["page_token"] == "page-2"

        return httpx.Response(
            status_code=200,
            json=second_payload,
        )

    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient

    def create_client(
        *args: Any,
        **kwargs: Any,
    ) -> httpx.AsyncClient:
        kwargs["transport"] = transport

        return original_async_client(
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        create_client,
    )

    provider = AlpacaProvider()

    result = await provider.get_history_many(
        tickers=[
            "msft",
            "AAPL",
            "AAPL",
        ],
        start=date(
            2026,
            8,
            17,
        ),
        end=date(
            2026,
            8,
            18,
        ),
    )

    assert list(result) == [
        "AAPL",
        "MSFT",
    ]

    assert len(result["AAPL"]) == 2

    assert len(result["MSFT"]) == 2

    assert result["AAPL"][0].date == date(
        2026,
        8,
        17,
    )

    assert result["AAPL"][1].date == date(
        2026,
        8,
        18,
    )

    assert result["AAPL"][1].close == Decimal("310.03")

    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("feed", ["iex", "sip"])
async def test_alpaca_passes_configured_feed(monkeypatch: pytest.MonkeyPatch, feed: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["feed"] == feed
        return httpx.Response(200, json={"bars": {"SPY": []}, "next_page_token": None})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def create_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", create_client)
    await AlpacaProvider(feed).get_history("SPY", date(2026, 8, 20), date(2026, 8, 20))


def test_alpaca_rejects_invalid_feed() -> None:
    with pytest.raises(ValueError, match="must be 'iex' or 'sip'"):
        AlpacaProvider("delayed")


@pytest.mark.asyncio
async def test_alpaca_403_is_safe_typed_feed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request, text="secret provider response")

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def create_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", create_client)
    with pytest.raises(MarketDataFeedNotAuthorizedError) as captured:
        await AlpacaProvider("sip").get_history("SPY", date(2026, 8, 20), date(2026, 8, 20))
    failure = captured.value.failure
    assert failure.code == "MARKET_DATA_FEED_NOT_AUTHORIZED"
    assert failure.provider == "Alpaca"
    assert failure.feed == "sip"
    assert "secret provider response" not in failure.message
