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
