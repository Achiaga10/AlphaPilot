from datetime import date

import pytest

from alphapilot.market.providers.polygon import PolygonProvider


@pytest.mark.asyncio
async def test_polygon_get_history() -> None:
    provider = PolygonProvider()

    candles = await provider.get_history(
        "AAPL",
        date(2026, 8, 1),
        date(2026, 8, 10),
    )

    assert isinstance(candles, list)

    if candles:
        candle = candles[0]

        assert candle.date is not None
        assert candle.open is not None
        assert candle.high is not None
        assert candle.low is not None
        assert candle.close is not None
        assert candle.volume >= 0
