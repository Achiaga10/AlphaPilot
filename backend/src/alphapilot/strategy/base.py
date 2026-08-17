from abc import ABC, abstractmethod

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.signal import Signal


class TradingStrategy(ABC):
    """Base interface for all trading strategies."""

    @abstractmethod
    def generate_signal(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> Signal:
        """Return BUY / SELL / HOLD."""
