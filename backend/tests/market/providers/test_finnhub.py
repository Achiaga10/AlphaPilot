from typing import Any

import httpx
import pytest

from alphapilot.market.providers.finnhub import (
    FinnhubProvider,
)


@pytest.mark.asyncio
async def test_get_index_constituents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "symbol": "^GSPC",
        "constituents": [
            "AAPL",
            "MSFT",
            "NVDA",
            "AMZN",
            "aapl",
            " MSFT ",
            "",
        ],
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"

        assert request.url.path == ("/api/v1/index/constituents")

        assert request.url.params["symbol"] == "^GSPC"

        return httpx.Response(
            status_code=200,
            json=payload,
        )

    transport = httpx.MockTransport(
        handler,
    )

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

    provider = FinnhubProvider()

    constituents = await provider.get_index_constituents(
        "^GSPC",
    )

    assert constituents == [
        "AAPL",
        "AMZN",
        "MSFT",
        "NVDA",
    ]


@pytest.mark.asyncio
async def test_get_company_metadata_normalizes_provider_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/stock/profile2"
        assert request.url.params["symbol"] == "SBET"
        return httpx.Response(
            200,
            json={
                "ticker": "SBET",
                "name": "SharpLink Gaming, Inc.",
                "exchange": "NASDAQ NMS - GLOBAL MARKET",
                "finnhubIndustry": "Media",
                "marketCapitalization": 125.5,
            },
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def create_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", create_client)
    result = await FinnhubProvider().get_company_metadata(" sbet ")
    assert result is not None
    assert result.ticker == "SBET"
    assert result.exchange == "NASDAQ"
    assert result.sector == "Media"
