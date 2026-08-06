from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.signal import Signal


class SMA20Strategy(TradingStrategy):
    """20-day Simple Moving Average strategy."""

    def generate_signal(
        self,
        company: Company,
        candles: list[DailyCandle],
    ) -> Signal:
        if len(candles) < 20:
            return Signal.HOLD

        closes = [c.close for c in candles[-20:]]

        sma = sum(closes) / Decimal(20)

        current_price = candles[-1].close

        previous_price = candles[-2].close

        if previous_price <= sma < current_price:
            return Signal.BUY

        if previous_price >= sma > current_price:
            return Signal.SELL

        return Signal.HOLD
