from __future__ import annotations

from alphapilot.backtesting.models import (
    BacktestPosition,
    BacktestResult,
    BacktestTrade,
    TradeSimulationResult,
)
from alphapilot.strategy.signal import Signal


class TradeSimulator:
    """Converts historical strategy signals into long trades."""

    def run(
        self,
        backtest: BacktestResult,
    ) -> TradeSimulationResult:
        trades: list[BacktestTrade] = []

        position: BacktestPosition | None = None

        bars = backtest.bars

        for index in range(len(bars) - 1):
            signal_bar = bars[index]

            execution_bar = bars[index + 1]

            if signal_bar.signal == Signal.BUY and position is None:
                position = BacktestPosition(
                    entry_signal_day=(signal_bar.trading_day),
                    entry_day=(execution_bar.trading_day),
                    entry_price=(execution_bar.open),
                )

                continue

            if signal_bar.signal == Signal.SELL and position is not None:
                trade = BacktestTrade(
                    entry_signal_day=(position.entry_signal_day),
                    entry_day=(position.entry_day),
                    entry_price=(position.entry_price),
                    exit_signal_day=(signal_bar.trading_day),
                    exit_day=(execution_bar.trading_day),
                    exit_price=(execution_bar.open),
                )

                trades.append(trade)

                position = None

        return TradeSimulationResult(
            ticker=backtest.ticker,
            trades=tuple(trades),
            open_position=position,
        )
