from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from alphapilot.market.providers.polygon import PolygonProvider


@pytest.mark.asyncio
async def test_polygon_get_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = PolygonProvider()

    timestamp_1 = int(
        datetime(
            2026,
            8,
            1,
            tzinfo=UTC,
        ).timestamp()
        * 1000
    )

    timestamp_2 = int(
        datetime(
            2026,
            8,
            2,
            tzinfo=UTC,
        ).timestamp()
        * 1000
    )

    payload = {
        "results": [
            {
                "t": timestamp_1,
                "o": 100.0,
                "h": 105.0,
                "l": 99.0,
                "c": 103.0,
                "v": 100000,
            },
            {
                "t": timestamp_2,
                "o": 103.0,
                "h": 108.0,
                "l": 102.0,
                "c": 107.0,
                "v": 120000,
            },
        ],
        "status": "OK",
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"
        assert "/v2/aggs/ticker/AAPL/range/1/day/" in str(request.url)

        return httpx.Response(
            status_code=200,
            json=payload,
        )

    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient

    def create_client(
        *args: object,
        **kwargs: object,
    ) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        create_client,
    )

    candles = await provider.get_history(
        ticker="AAPL",
        start=date(2026, 8, 1),
        end=date(2026, 8, 2),
    )

    assert len(candles) == 2

    assert candles[0].date == date(2026, 8, 1)
    assert candles[0].open == Decimal("100.0")
    assert candles[0].high == Decimal("105.0")
    assert candles[0].low == Decimal("99.0")
    assert candles[0].close == Decimal("103.0")
    assert candles[0].volume == 100000

    assert candles[1].date == date(2026, 8, 2)
    assert candles[1].open == Decimal("103.0")
    assert candles[1].high == Decimal("108.0")
    assert candles[1].low == Decimal("102.0")
    assert candles[1].close == Decimal("107.0")
    assert candles[1].volume == 120000
