from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MarketDataProviderFailure:
    code: str
    provider: str
    feed: str | None
    message: str


class MarketDataProviderError(RuntimeError):
    """Safe provider failure suitable for domain/API attribution."""

    def __init__(self, failure: MarketDataProviderFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


class MarketDataFeedNotAuthorizedError(MarketDataProviderError):
    pass
