from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.indicators import calculate_ema_series
from alphapilot.strategy.signal import Signal


class EMA20PullbackStrategy(TradingStrategy):
    """EMA20 trend-pullback strategy."""

    EMA_FAST_PERIOD = 20
    EMA_SLOW_PERIOD = 50

    SLOPE_LOOKBACK = 5

    PULLBACK_LOWER_BOUND = Decimal("0.97")
    PULLBACK_UPPER_BOUND = Decimal("1.01")

    MIN_CANDLES = EMA_SLOW_PERIOD + SLOPE_LOOKBACK

    def generate_signal(
        self,
        company: Company,
        candles: list[DailyCandle],
    ) -> Signal:
        if len(candles) < self.MIN_CANDLES:
            return Signal.HOLD

        ordered_candles = sorted(
            candles,
            key=lambda candle: candle.trading_day,
        )

        closes = [candle.close for candle in ordered_candles]

        ema20_values = calculate_ema_series(
            closes,
            self.EMA_FAST_PERIOD,
        )

        ema50_values = calculate_ema_series(
            closes,
            self.EMA_SLOW_PERIOD,
        )

        if not ema20_values or not ema50_values:
            return Signal.HOLD

        current_candle = ordered_candles[-1]

        current_ema20 = ema20_values[-1]
        current_ema50 = ema50_values[-1]

        previous_ema20 = ema20_values[-(self.SLOPE_LOOKBACK + 1)]

        #
        # SELL
        #
        # A close below EMA50 represents a trend breakdown.
        #
        if current_candle.close < current_ema50:
            return Signal.SELL

        #
        # TREND FILTER
        #
        ema20_above_ema50 = current_ema20 > current_ema50

        ema20_rising = current_ema20 > previous_ema20

        bullish_trend = ema20_above_ema50 and ema20_rising

        if not bullish_trend:
            return Signal.HOLD

        #
        # PULLBACK
        #
        pullback_lower = current_ema20 * self.PULLBACK_LOWER_BOUND

        pullback_upper = current_ema20 * self.PULLBACK_UPPER_BOUND

        touched_ema20_zone = pullback_lower <= current_candle.low <= pullback_upper

        #
        # CONFIRMATION
        #
        reclaimed_ema20 = current_candle.close >= current_ema20

        if touched_ema20_zone and reclaimed_ema20:
            return Signal.BUY

        return Signal.HOLD
