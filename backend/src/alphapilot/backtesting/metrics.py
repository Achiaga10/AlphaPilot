from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from alphapilot.backtesting.models import (
    TradeSimulationResult,
)


@dataclass(slots=True, frozen=True)
class PerformanceMetrics:
    """Performance statistics calculated from completed trades."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    win_rate_pct: Decimal

    average_return_pct: Decimal | None
    average_win_pct: Decimal | None
    average_loss_pct: Decimal | None

    best_trade_pct: Decimal | None
    worst_trade_pct: Decimal | None

    gross_profit_pct: Decimal
    gross_loss_pct: Decimal

    profit_factor: Decimal | None

    compounded_return_pct: Decimal


class PerformanceMetricsCalculator:
    """Calculates performance metrics from completed trades."""

    def calculate(
        self,
        simulation: TradeSimulationResult,
    ) -> PerformanceMetrics:
        returns = [trade.return_pct for trade in simulation.trades]

        if not returns:
            return self._empty_metrics()

        winning_returns = [value for value in returns if value > 0]

        losing_returns = [value for value in returns if value < 0]

        breakeven_returns = [value for value in returns if value == 0]

        total_trades = len(returns)

        winning_trades = len(winning_returns)

        losing_trades = len(losing_returns)

        breakeven_trades = len(breakeven_returns)

        win_rate_pct = Decimal(winning_trades) / Decimal(total_trades) * Decimal("100")

        average_return_pct = sum(
            returns,
            Decimal("0"),
        ) / Decimal(total_trades)

        average_win_pct = (
            sum(
                winning_returns,
                Decimal("0"),
            )
            / Decimal(winning_trades)
            if winning_returns
            else None
        )

        average_loss_pct = (
            sum(
                losing_returns,
                Decimal("0"),
            )
            / Decimal(losing_trades)
            if losing_returns
            else None
        )

        gross_profit_pct = sum(
            winning_returns,
            Decimal("0"),
        )

        gross_loss_pct = abs(
            sum(
                losing_returns,
                Decimal("0"),
            )
        )

        profit_factor = gross_profit_pct / gross_loss_pct if gross_loss_pct > 0 else None

        compounded_multiplier = Decimal("1")

        for return_pct in returns:
            compounded_multiplier *= Decimal("1") + return_pct / Decimal("100")

        compounded_return_pct = (compounded_multiplier - Decimal("1")) * Decimal("100")

        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate_pct=win_rate_pct,
            average_return_pct=average_return_pct,
            average_win_pct=average_win_pct,
            average_loss_pct=average_loss_pct,
            best_trade_pct=max(returns),
            worst_trade_pct=min(returns),
            gross_profit_pct=gross_profit_pct,
            gross_loss_pct=gross_loss_pct,
            profit_factor=profit_factor,
            compounded_return_pct=(compounded_return_pct),
        )

    @staticmethod
    def _empty_metrics() -> PerformanceMetrics:
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            win_rate_pct=Decimal("0"),
            average_return_pct=None,
            average_win_pct=None,
            average_loss_pct=None,
            best_trade_pct=None,
            worst_trade_pct=None,
            gross_profit_pct=Decimal("0"),
            gross_loss_pct=Decimal("0"),
            profit_factor=None,
            compounded_return_pct=Decimal("0"),
        )
