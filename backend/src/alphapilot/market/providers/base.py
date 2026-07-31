from abc import ABC, abstractmethod
from typing import Any


class MarketProvider(ABC):
    @abstractmethod
    async def get_quote(self, ticker: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_history(self, ticker: str) -> list[dict[str, Any]]: ...
