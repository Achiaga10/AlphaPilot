from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from alphapilot.backtesting.diagnostics import (
    BacktestDiagnostics,
    TradeDiagnostic,
)
from alphapilot.strategy.evaluation import SignalReason


@dataclass(slots=True, frozen=True)
class EntryReasonPerformance:
    """Performance of completed trades opened by one entry reason."""

    reason: SignalReason

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    win_rate_pct: Decimal | None

    average_trade_pct: Decimal | None
    average_win_pct: Decimal | None
    average_loss_pct: Decimal | None

    profit_factor: Decimal | None
    compounded_return_pct: Decimal | None

    average_holding_days: Decimal | None

    average_mfe_pct: Decimal | None
    average_mae_pct: Decimal | None
    average_peak_giveback_pct: Decimal | None


class EntryReasonPerformanceCalculator:
    """Calculates completed-trade metrics grouped by entry reason."""

    def calculate(
        self,
        diagnostics: BacktestDiagnostics,
        *,
        reason: SignalReason,
    ) -> EntryReasonPerformance:
        trades = [trade for trade in diagnostics.trades if trade.entry_reason == reason]

        if not trades:
            return EntryReasonPerformance(
                reason=reason,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                breakeven_trades=0,
                win_rate_pct=None,
                average_trade_pct=None,
                average_win_pct=None,
                average_loss_pct=None,
                profit_factor=None,
                compounded_return_pct=None,
                average_holding_days=None,
                average_mfe_pct=None,
                average_mae_pct=None,
                average_peak_giveback_pct=None,
            )

        winning_trades = [trade for trade in trades if trade.return_pct > 0]

        losing_trades = [trade for trade in trades if trade.return_pct < 0]

        breakeven_trades = [trade for trade in trades if trade.return_pct == 0]

        count = Decimal(len(trades))

        win_rate_pct = Decimal(len(winning_trades)) / count * Decimal("100")

        average_trade_pct = self._average([trade.return_pct for trade in trades])

        average_win_pct = self._average([trade.return_pct for trade in winning_trades])

        average_loss_pct = self._average([trade.return_pct for trade in losing_trades])

        gross_profit = sum(
            (trade.return_pct for trade in winning_trades),
            Decimal("0"),
        )

        gross_loss = abs(
            sum(
                (trade.return_pct for trade in losing_trades),
                Decimal("0"),
            )
        )

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

        compounded_return_pct = self._calculate_compounded_return(trades)

        average_holding_days = self._average([Decimal(trade.holding_days) for trade in trades])

        average_mfe_pct = self._average([trade.mfe_pct for trade in trades])

        average_mae_pct = self._average([trade.mae_pct for trade in trades])

        average_peak_giveback_pct = self._average([trade.peak_giveback_pct for trade in trades])

        return EntryReasonPerformance(
            reason=reason,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            breakeven_trades=len(breakeven_trades),
            win_rate_pct=win_rate_pct,
            average_trade_pct=average_trade_pct,
            average_win_pct=average_win_pct,
            average_loss_pct=average_loss_pct,
            profit_factor=profit_factor,
            compounded_return_pct=(compounded_return_pct),
            average_holding_days=(average_holding_days),
            average_mfe_pct=average_mfe_pct,
            average_mae_pct=average_mae_pct,
            average_peak_giveback_pct=(average_peak_giveback_pct),
        )

    def _average(
        self,
        values: list[Decimal],
    ) -> Decimal | None:
        if not values:
            return None

        return sum(
            values,
            Decimal("0"),
        ) / Decimal(len(values))

    def _calculate_compounded_return(
        self,
        trades: list[TradeDiagnostic],
    ) -> Decimal:
        growth = Decimal("1")

        for trade in trades:
            growth *= Decimal("1") + trade.return_pct / Decimal("100")

        return (growth - Decimal("1")) * Decimal("100")
