from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from alphapilot.market.dto import MarketCandle


class MarketProvider(ABC):
    @abstractmethod
    async def get_quote(
        self,
        ticker: str,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_history(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> list[MarketCandle]: ...
