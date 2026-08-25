from __future__ import annotations

from datetime import date
from decimal import Decimal

from alphapilot.database.models.daily_candle import DailyCandle


class RelativeStrength20Calculator:
    """Calculates fixed 20-trading-bar stock return minus SPY return."""

    LOOKBACK_BARS = 20
    REQUIRED_CLOSES = LOOKBACK_BARS + 1

    def calculate(
        self,
        *,
        stock_candles: list[DailyCandle],
        benchmark_candles: list[DailyCandle],
        signal_day: date,
    ) -> Decimal | None:
        stock_closes = self._available_closes(stock_candles, signal_day)
        benchmark_closes = self._available_closes(benchmark_candles, signal_day)

        if len(stock_closes) < self.REQUIRED_CLOSES or len(benchmark_closes) < self.REQUIRED_CLOSES:
            return None

        stock_lookback_close = stock_closes[-self.REQUIRED_CLOSES]
        benchmark_lookback_close = benchmark_closes[-self.REQUIRED_CLOSES]

        if stock_lookback_close == 0 or benchmark_lookback_close == 0:
            return None

        stock_return = stock_closes[-1] / stock_lookback_close - Decimal("1")
        benchmark_return = benchmark_closes[-1] / benchmark_lookback_close - Decimal("1")

        return stock_return - benchmark_return

    @staticmethod
    def _available_closes(
        candles: list[DailyCandle],
        signal_day: date,
    ) -> list[Decimal]:
        return [
            candle.close
            for candle in sorted(candles, key=lambda item: item.trading_day)
            if candle.trading_day <= signal_day
        ]
