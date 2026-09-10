from __future__ import annotations

from datetime import date
from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.indicators import calculate_ema_series
from alphapilot.strategy.signal import Signal


class AchiaStratEMA20Strategy(TradingStrategy):
    """One frozen research-only long hypothesis; never registered as a live profile."""

    STRATEGY_ID = "achia-strat-ema20-v1"
    VERSION = 1
    DISPLAY_NAME = "Achia_strat_ema20"
    EMA_FAST = 20
    EMA_SLOW = 50
    MIN_CANDLES = EMA_SLOW
    ENTRY_LOWER_MULTIPLIER = Decimal("0.90")
    ENTRY_UPPER_MULTIPLIER = Decimal("1.01")

    def __init__(self, session_policy: CompletedDailySessionPolicy | None = None) -> None:
        self.session_policy = session_policy or CompletedDailySessionPolicy()

    def evaluate(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> StrategyEvaluation:
        del company, context
        return self.evaluate_as_of(candles, signal_day=self.session_policy.completed_through())

    def evaluate_as_of(self, candles: list[DailyCandle], *, signal_day: date) -> StrategyEvaluation:
        through = min(signal_day, self.session_policy.completed_through())
        available = sorted(
            (candle for candle in candles if candle.trading_day <= through),
            key=lambda candle: candle.trading_day,
        )
        if not available:
            return StrategyEvaluation(Signal.HOLD, SignalReason.INSUFFICIENT_DATA)
        if len({candle.trading_day for candle in available}) != len(available) or any(
            not self.valid_candle(candle) for candle in available
        ):
            return StrategyEvaluation(Signal.HOLD, SignalReason.INVALID_CANDLE_DATA)
        if len(available) < self.MIN_CANDLES:
            return StrategyEvaluation(Signal.HOLD, SignalReason.INSUFFICIENT_DATA)
        closes = [candle.close for candle in available]
        return self.evaluate_indicators(
            close=closes[-1],
            ema20=calculate_ema_series(closes, self.EMA_FAST)[-1],
            ema50=calculate_ema_series(closes, self.EMA_SLOW)[-1],
        )

    @staticmethod
    def valid_candle(candle: DailyCandle) -> bool:
        values = (candle.open, candle.high, candle.low, candle.close)
        return (
            all(isinstance(value, Decimal) and value.is_finite() and value > 0 for value in values)
            and candle.low <= min(candle.open, candle.close)
            and candle.high >= max(candle.open, candle.close)
        )

    @classmethod
    def evaluate_indicators(
        cls, *, close: Decimal, ema20: Decimal, ema50: Decimal
    ) -> StrategyEvaluation:
        if any(not value.is_finite() or value <= 0 for value in (close, ema20, ema50)):
            return StrategyEvaluation(Signal.HOLD, SignalReason.INVALID_CANDLE_DATA)
        entry = (
            ema20 > ema50
            and cls.ENTRY_LOWER_MULTIPLIER * ema20 <= close <= cls.ENTRY_UPPER_MULTIPLIER * ema20
        )
        exit_reason = SignalReason.CLOSE_BELOW_EMA20 if close < ema20 else None
        return StrategyEvaluation(
            signal=Signal.BUY if entry else Signal.SELL if exit_reason else Signal.HOLD,
            reason=(SignalReason.ACHIA_EMA20_ENTRY_ZONE if entry else exit_reason)
            or SignalReason.ACHIA_EMA20_NO_ENTRY,
            ema20=ema20,
            ema50=ema50,
            position_exit_reason=exit_reason,
        )
