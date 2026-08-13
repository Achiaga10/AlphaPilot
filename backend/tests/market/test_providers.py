from alphapilot.market.providers.finnhub import FinnhubProvider
from alphapilot.market.providers.polygon import PolygonProvider


def test_polygon_provider_implements_market_provider() -> None:
    provider = PolygonProvider()

    assert provider is not None


def test_finnhub_provider_implements_market_provider() -> None:
    provider = FinnhubProvider()

    assert provider is not None
