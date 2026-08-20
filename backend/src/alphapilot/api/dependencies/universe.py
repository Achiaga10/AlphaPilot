from alphapilot.market.providers.base import (
    IndexConstituentDetailsProvider,
    IndexConstituentsProvider,
)
from alphapilot.market.providers.wikipedia import (
    WikipediaIndexConstituentsProvider,
)


def get_index_constituents_provider() -> IndexConstituentsProvider:
    return WikipediaIndexConstituentsProvider()


def get_index_constituent_details_provider() -> IndexConstituentDetailsProvider:
    return WikipediaIndexConstituentsProvider()
