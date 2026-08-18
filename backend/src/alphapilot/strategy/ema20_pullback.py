from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import (
    MarketRegime,
    SignalReason,
    StrategyEvaluation,
)
from alphapilot.strategy.indicators import (
    calculate_ema_series,
    calculate_sma,
)
from alphapilot.strategy.signal import Signal


class EMA20PullbackStrategy(TradingStrategy):
    """EMA20 trend-pullback strategy with market regime filter."""

    EMA_FAST_PERIOD = 20
    EMA_SLOW_PERIOD = 50

    MARKET_SMA_PERIOD = 200

    SLOPE_LOOKBACK = 5

    PULLBACK_LOWER_BOUND = Decimal("0.97")
    PULLBACK_UPPER_BOUND = Decimal("1.01")

    MIN_CANDLES = EMA_SLOW_PERIOD + SLOPE_LOOKBACK

    def evaluate(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> StrategyEvaluation:
        market_regime = self._get_market_regime(
            context,
        )

        if len(candles) < self.MIN_CANDLES:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.INSUFFICIENT_DATA,
                market_regime=market_regime,
            )

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
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.INSUFFICIENT_DATA,
                market_regime=market_regime,
            )

        current_candle = ordered_candles[-1]

        current_ema20 = ema20_values[-1]
        current_ema50 = ema50_values[-1]

        previous_ema20 = ema20_values[-(self.SLOPE_LOOKBACK + 1)]

        #
        # EXIT
        #
        # A market filter must never prevent a SELL.
        #
        if current_candle.close < current_ema50:
            return StrategyEvaluation(
                signal=Signal.SELL,
                reason=SignalReason.TREND_BREAKDOWN,
                ema20=current_ema20,
                ema50=current_ema50,
                market_regime=market_regime,
            )

        #
        # MARKET REGIME
        #
        if market_regime != MarketRegime.BULLISH:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.MARKET_REGIME_BLOCKED,
                ema20=current_ema20,
                ema50=current_ema50,
                market_regime=market_regime,
            )

        #
        # STOCK TREND
        #
        ema20_above_ema50 = current_ema20 > current_ema50

        ema20_rising = current_ema20 > previous_ema20

        if not (ema20_above_ema50 and ema20_rising):
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.STOCK_TREND_NOT_BULLISH,
                ema20=current_ema20,
                ema50=current_ema50,
                market_regime=market_regime,
            )

        #
        # PULLBACK ZONE
        #
        pullback_lower = current_ema20 * self.PULLBACK_LOWER_BOUND

        pullback_upper = current_ema20 * self.PULLBACK_UPPER_BOUND

        touched_ema20_zone = pullback_lower <= current_candle.low <= pullback_upper

        if not touched_ema20_zone:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.NO_PULLBACK,
                ema20=current_ema20,
                ema50=current_ema50,
                market_regime=market_regime,
            )

        #
        # RECLAIM / CONFIRMATION
        #
        reclaimed_ema20 = current_candle.close >= current_ema20

        if not reclaimed_ema20:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.PULLBACK_NOT_CONFIRMED,
                ema20=current_ema20,
                ema50=current_ema50,
                market_regime=market_regime,
            )

        return StrategyEvaluation(
            signal=Signal.BUY,
            reason=SignalReason.EMA20_PULLBACK_RECLAIM,
            ema20=current_ema20,
            ema50=current_ema50,
            market_regime=market_regime,
        )

    def _get_market_regime(
        self,
        context: StrategyContext | None,
    ) -> MarketRegime:
        if context is None:
            return MarketRegime.UNKNOWN

        benchmark_candles = sorted(
            context.benchmark_candles,
            key=lambda candle: candle.trading_day,
        )

        if len(benchmark_candles) < self.MARKET_SMA_PERIOD:
            return MarketRegime.UNKNOWN

        benchmark_closes = [candle.close for candle in benchmark_candles]

        sma200 = calculate_sma(
            benchmark_closes,
            self.MARKET_SMA_PERIOD,
        )

        if sma200 is None:
            return MarketRegime.UNKNOWN

        current_market_price = benchmark_candles[-1].close

        if current_market_price > sma200:
            return MarketRegime.BULLISH

        if current_market_price < sma200:
            return MarketRegime.BEARISH

        return MarketRegime.NEUTRAL
