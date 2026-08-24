from __future__ import annotations

from datetime import date

from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
)
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext


class BacktestingEngine:
    """Replays historical candles through a trading strategy."""

    def __init__(
        self,
        strategy: TradingStrategy,
    ) -> None:
        self.strategy = strategy

    def run(
        self,
        company: Company,
        candles: list[DailyCandle],
        *,
        benchmark_ticker: str,
        benchmark_candles: list[DailyCandle],
        start: date | None = None,
        end: date | None = None,
    ) -> BacktestResult:
        ordered_candles = sorted(
            candles,
            key=lambda candle: candle.trading_day,
        )

        ordered_benchmark = sorted(
            benchmark_candles,
            key=lambda candle: candle.trading_day,
        )

        evaluation_candles = [
            candle
            for candle in ordered_candles
            if self._is_in_backtest_range(
                candle.trading_day,
                start=start,
                end=end,
            )
        ]

        results: list[BacktestBarResult] = []

        for current_candle in evaluation_candles:
            current_day = current_candle.trading_day

            available_stock_candles = [
                candle for candle in ordered_candles if candle.trading_day <= current_day
            ]

            available_benchmark_candles = [
                candle for candle in ordered_benchmark if candle.trading_day <= current_day
            ]

            context = StrategyContext(
                benchmark_ticker=benchmark_ticker,
                benchmark_candles=tuple(available_benchmark_candles),
            )

            evaluation = self.strategy.evaluate(
                company,
                available_stock_candles,
                context,
            )

            results.append(
                BacktestBarResult(
                    trading_day=current_day,
                    open=current_candle.open,
                    close=current_candle.close,
                    evaluation=evaluation,
                )
            )

        result_start = results[0].trading_day if results else None

        result_end = results[-1].trading_day if results else None

        return BacktestResult(
            ticker=company.ticker,
            start=result_start,
            end=result_end,
            bars=tuple(results),
        )

    @staticmethod
    def _is_in_backtest_range(
        trading_day: date,
        *,
        start: date | None,
        end: date | None,
    ) -> bool:
        if start is not None and trading_day < start:
            return False

        if end is not None and trading_day > end:
            return False

        return True
