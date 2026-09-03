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
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.indicators import (
    calculate_ema_series,
    calculate_sma,
)
from alphapilot.strategy.signal import Signal

EMA20_PULLBACK_LOWER_BOUND = Decimal("0.97")
EMA20_PULLBACK_UPPER_BOUND = Decimal("1.01")


class EMA20PullbackStrategy(TradingStrategy):
    """EMA20 trend-pullback strategy with market regime filter."""

    EMA_FAST_PERIOD = 20
    EMA_SLOW_PERIOD = 50

    MARKET_SMA_PERIOD = 200

    SLOPE_LOOKBACK = 5

    PULLBACK_LOWER_BOUND = EMA20_PULLBACK_LOWER_BOUND
    PULLBACK_UPPER_BOUND = EMA20_PULLBACK_UPPER_BOUND

    MIN_CANDLES = EMA_SLOW_PERIOD + SLOPE_LOOKBACK

    def __init__(
        self,
        exit_mode: TrendExitMode = TrendExitMode.EMA50,
        hybrid_trend_threshold_pct: Decimal = Decimal("3"),
    ) -> None:
        if hybrid_trend_threshold_pct < 0:
            raise ValueError("hybrid_trend_threshold_pct must not be negative")

        self.exit_mode = exit_mode
        self.hybrid_trend_threshold_pct = hybrid_trend_threshold_pct

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
        exit_reason = self._get_exit_reason(
            close=current_candle.close,
            ema20=current_ema20,
            ema50=current_ema50,
        )

        if exit_reason is not None:
            return StrategyEvaluation(
                signal=Signal.SELL,
                reason=exit_reason,
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

    def _get_exit_reason(
        self,
        *,
        close: Decimal,
        ema20: Decimal,
        ema50: Decimal,
    ) -> SignalReason | None:
        if self.exit_mode == TrendExitMode.EMA20:
            if close < ema20:
                return SignalReason.EMA20_TREND_BREAKDOWN

            return None

        if self.exit_mode == TrendExitMode.EMA50:
            if close < ema50:
                return SignalReason.TREND_BREAKDOWN

            return None

        #
        # HYBRID EXIT
        #
        # EMA50 remains the hard trend-break exit.
        #
        if close < ema50:
            return SignalReason.TREND_BREAKDOWN

        #
        # Above EMA20 there is no exit.
        #
        if close >= ema20:
            return None

        #
        # Price is below EMA20 but still above EMA50.
        #
        # In a strong trend we allow additional room and wait
        # for EMA50. In a weaker trend we exit on EMA20.
        #
        if self._is_strong_trend(
            ema20=ema20,
            ema50=ema50,
        ):
            return None

        return SignalReason.EMA20_TREND_BREAKDOWN

    def _is_strong_trend(
        self,
        *,
        ema20: Decimal,
        ema50: Decimal,
    ) -> bool:
        if ema50 <= 0:
            return False

        spread_pct = (ema20 - ema50) / ema50 * Decimal("100")

        return spread_pct >= self.hybrid_trend_threshold_pct

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
