from typing import Any

import httpx
import pytest

from alphapilot.core.config import settings
from alphapilot.market.providers.wikipedia import (
    WikipediaIndexConstituentsProvider,
)


@pytest.mark.asyncio
async def test_get_index_constituents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wikitext = """
== S&P 500 component stocks ==

{| class="wikitable sortable" id="constituents"
|-
! Symbol !! Security
|-
|| {{NyseSymbol|MMM}}
|| 3M
|-
|| {{NasdaqSymbol|AAPL}}
|| Apple
|-
|| {{NyseSymbol|BRK.B}}
|| Berkshire Hathaway
|-
|| {{NasdaqSymbol|NVDA}}
|| Nvidia
|}

== Selected changes ==

{| class="wikitable"
|-
|| {{NyseSymbol|OLD}}
|| Historical value
|}
"""

    payload = {
        "parse": {
            "title": ("List of S&P 500 companies"),
            "wikitext": wikitext,
        }
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"

        assert request.url.params["action"] == "parse"

        assert request.url.params["prop"] == "wikitext"

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
        httpx,
        "AsyncClient",
        create_client,
    )
    monkeypatch.setattr(
        settings,
        "WIKIMEDIA_USER_AGENT",
        "AlphaPilotTest/0.1",
    )
    provider = WikipediaIndexConstituentsProvider()

    tickers = await provider.get_index_constituents("^GSPC")

    assert tickers == [
        "AAPL",
        "BRK.B",
        "MMM",
        "NVDA",
    ]

    assert "OLD" not in tickers
