from decimal import Decimal

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import (
    SignalReason,
    StrategyEvaluation,
)
from alphapilot.strategy.signal import Signal


class SMA20Strategy(TradingStrategy):
    """20-day simple moving average crossover strategy."""

    PERIOD = 20

    def evaluate(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> StrategyEvaluation:
        if len(candles) < self.PERIOD + 1:
            return StrategyEvaluation(
                signal=Signal.HOLD,
                reason=SignalReason.INSUFFICIENT_DATA,
            )

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
            return StrategyEvaluation(
                signal=Signal.BUY,
                reason=SignalReason.SMA20_CROSS_UP,
            )

        if previous_price >= previous_sma and current_price < current_sma:
            return StrategyEvaluation(
                signal=Signal.SELL,
                reason=SignalReason.SMA20_CROSS_DOWN,
            )

        return StrategyEvaluation(
            signal=Signal.HOLD,
            reason=SignalReason.NO_SMA20_CROSS,
        )
