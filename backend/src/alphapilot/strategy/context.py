from dataclasses import dataclass

from alphapilot.database.models.daily_candle import DailyCandle


@dataclass(slots=True, frozen=True)
class StrategyContext:
    """External market context available to a trading strategy."""

    benchmark_ticker: str
    benchmark_candles: tuple[DailyCandle, ...]
