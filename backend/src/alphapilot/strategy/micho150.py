from __future__ import annotations

from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import (
    SignalReason,
    StrategyEvaluation,
)
from alphapilot.strategy.indicators import calculate_sma
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.signal import Signal


class Micho150Strategy(TradingStrategy):
    """
    Mechanical interpretation of the publicly described
    Micha.Stocks / Micho moving-average strategy.

    V1 rules:
    - Use SMA150 as the long-term trend reference.
    - Only consider entries when SMA150 is flat or rising.
    - BUY on a breakout above SMA150.
    - BUY on a touch/bounce from the SMA150 area.
    - SELL on a close below SMA150.

    Entry modes:
    - BOTH: preserve the original V1 behavior.
    - BREAKOUT_ONLY: allow only breakout entries.
    - BOUNCE_ONLY: allow only bounce entries.

    This implementation intentionally excludes discretionary
    chart-pattern analysis, news, volume and stop management.
    """

    MA_PERIOD = 150
    SLOPE_LOOKBACK = 5

    TOUCH_LOWER_BOUND = Decimal("0.98")
    TOUCH_UPPER_BOUND = Decimal("1.02")

    MIN_CANDLES = MA_PERIOD + SLOPE_LOOKBACK

    def __init__(
        self,
        entry_mode: MichoEntryMode = MichoEntryMode.BOTH,
    ) -> None:
        self.entry_mode = entry_mode

    def evaluate(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> StrategyEvaluation:
        del company
        del context

        if len(candles) < self.MIN_CANDLES:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.INSUFFICIENT_DATA,
            )

        ordered_candles = sorted(
            candles,
            key=lambda candle: candle.trading_day,
        )

        current_candle = ordered_candles[-1]
        previous_candle = ordered_candles[-2]

        current_sma150 = self._calculate_sma150(ordered_candles)

        previous_sma150 = self._calculate_sma150(ordered_candles[:-1])

        slope_reference_sma150 = self._calculate_sma150(ordered_candles[: -self.SLOPE_LOOKBACK])

        if current_sma150 is None or previous_sma150 is None or slope_reference_sma150 is None:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.INSUFFICIENT_DATA,
            )

        #
        # EXIT
        #
        # Exit behavior remains identical across all
        # Micho entry modes.
        #
        if current_candle.close < current_sma150:
            return StrategyEvaluation(
                signal=Signal.SELL,
                reason=SignalReason.MICHO_150_BREAKDOWN,
                sma150=current_sma150,
            )

        #
        # TREND FILTER
        #
        sma150_flat_or_rising = current_sma150 >= slope_reference_sma150

        if not sma150_flat_or_rising:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=(SignalReason.MICHO_150_TREND_NOT_READY),
                sma150=current_sma150,
            )

        #
        # BREAKOUT
        #
        crossed_above = (
            previous_candle.close <= previous_sma150 and current_candle.close > current_sma150
        )

        if crossed_above:
            if self.entry_mode in (
                MichoEntryMode.BOTH,
                MichoEntryMode.BREAKOUT_ONLY,
            ):
                return StrategyEvaluation(
                    signal=Signal.BUY,
                    reason=(SignalReason.MICHO_150_BREAKOUT),
                    sma150=current_sma150,
                )

            #
            # Important:
            # In BOUNCE_ONLY we stop here.
            #
            # The same trading day must not later be
            # reclassified as a bounce merely because
            # it also touched the SMA150 zone.
            #
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.MICHO_150_NO_ENTRY,
                sma150=current_sma150,
            )

        #
        # BREAKOUT_ONLY does not evaluate bounce entries.
        #
        if self.entry_mode == MichoEntryMode.BREAKOUT_ONLY:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.MICHO_150_NO_ENTRY,
                sma150=current_sma150,
            )

        #
        # TOUCH / BOUNCE
        #
        touch_lower = current_sma150 * self.TOUCH_LOWER_BOUND

        touch_upper = current_sma150 * self.TOUCH_UPPER_BOUND

        touched_ma150 = touch_lower <= current_candle.low <= touch_upper

        bounced_above = (
            current_candle.close > current_sma150 and current_candle.close > previous_candle.close
        )

        if touched_ma150 and bounced_above:
            return StrategyEvaluation(
                signal=Signal.BUY,
                reason=SignalReason.MICHO_150_BOUNCE,
                sma150=current_sma150,
            )

        return StrategyEvaluation(
            signal=Signal.HOLD,
            reason=SignalReason.MICHO_150_NO_ENTRY,
            sma150=current_sma150,
        )

    def _calculate_sma150(
        self,
        candles: list[DailyCandle],
    ) -> Decimal | None:
        closes = [candle.close for candle in candles]

        return calculate_sma(
            closes,
            self.MA_PERIOD,
        )
