from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.signal import Signal


class SMA20Strategy(TradingStrategy):
    """20-day simple moving average crossover strategy."""

    PERIOD = 20

    def generate_signal(
        self,
        company: Company,
        candles: list[DailyCandle],
    ) -> Signal:
        if len(candles) < self.PERIOD + 1:
            return Signal.HOLD

        ordered_candles = sorted(
            candles,
            key=lambda candle: candle.trading_day,
        )

        previous_window = ordered_candles[-(self.PERIOD + 1) : -1]

        current_window = ordered_candles[-self.PERIOD :]

        previous_sma = sum(
            (candle.close for candle in previous_window),
            Decimal(0),
        ) / Decimal(self.PERIOD)

        current_sma = sum(
            (candle.close for candle in current_window),
            Decimal(0),
        ) / Decimal(self.PERIOD)

        previous_price = ordered_candles[-2].close
        current_price = ordered_candles[-1].close

        if previous_price <= previous_sma and current_price > current_sma:
            return Signal.BUY

        if previous_price >= previous_sma and current_price < current_sma:
            return Signal.SELL

        return Signal.HOLD
