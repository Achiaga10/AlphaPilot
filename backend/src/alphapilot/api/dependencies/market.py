from alphapilot.market.providers.base import MarketProvider
from alphapilot.market.providers.polygon import PolygonProvider


def get_market_provider() -> MarketProvider:
    return PolygonProvider()
