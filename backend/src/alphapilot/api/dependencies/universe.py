from alphapilot.market.providers.base import (
    IndexConstituentsProvider,
)
from alphapilot.market.providers.finnhub import (
    FinnhubProvider,
)


def get_index_constituents_provider() -> IndexConstituentsProvider:
    return FinnhubProvider()
