from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from alphapilot.backtesting.models import (
    BacktestResult,
    PortfolioSimulationResult,
)
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.evaluation import SignalReason


@dataclass(slots=True, frozen=True)
class TradeDiagnostic:
    entry_day: date
    exit_day: date

    entry_price: Decimal
    exit_price: Decimal

    return_pct: Decimal

    holding_days: int

    mfe_pct: Decimal
    mae_pct: Decimal

    peak_giveback_pct: Decimal

    entry_reason: SignalReason | None
    exit_reason: SignalReason | None


@dataclass(slots=True, frozen=True)
class BacktestDiagnostics:
    trades: tuple[TradeDiagnostic, ...]

    average_mfe_pct: Decimal | None
    average_mae_pct: Decimal | None
    average_peak_giveback_pct: Decimal | None


class BacktestDiagnosticsCalculator:
    """Analyzes trade behavior between entry and exit."""

    def calculate(
        self,
        backtest: BacktestResult,
        portfolio: PortfolioSimulationResult,
        candles: list[DailyCandle],
    ) -> BacktestDiagnostics:
        bars_by_day = {bar.trading_day: bar for bar in backtest.bars}

        ordered_candles = sorted(
            candles,
            key=lambda candle: candle.trading_day,
        )

        diagnostics: list[TradeDiagnostic] = []

        for trade in portfolio.trades:
            holding_candles = [
                candle
                for candle in ordered_candles
                if (trade.entry_day <= candle.trading_day < trade.exit_day)
            ]

            observed_highs = [
                trade.entry_price,
                trade.exit_price,
                *[candle.high for candle in holding_candles],
            ]

            observed_lows = [
                trade.entry_price,
                trade.exit_price,
                *[candle.low for candle in holding_candles],
            ]

            peak_price = max(observed_highs)

            trough_price = min(observed_lows)

            mfe_pct = (peak_price - trade.entry_price) / trade.entry_price * Decimal("100")

            mae_pct = (trough_price - trade.entry_price) / trade.entry_price * Decimal("100")

            peak_giveback_pct = (
                (peak_price - trade.exit_price) / peak_price * Decimal("100")
                if peak_price > 0
                else Decimal("0")
            )

            entry_bar = bars_by_day.get(trade.entry_signal_day)

            exit_bar = bars_by_day.get(trade.exit_signal_day)

            diagnostics.append(
                TradeDiagnostic(
                    entry_day=trade.entry_day,
                    exit_day=trade.exit_day,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    return_pct=trade.return_pct,
                    holding_days=(trade.exit_day - trade.entry_day).days,
                    mfe_pct=mfe_pct,
                    mae_pct=mae_pct,
                    peak_giveback_pct=(peak_giveback_pct),
                    entry_reason=(entry_bar.evaluation.reason if entry_bar is not None else None),
                    exit_reason=(exit_bar.evaluation.reason if exit_bar is not None else None),
                )
            )

        if not diagnostics:
            return BacktestDiagnostics(
                trades=(),
                average_mfe_pct=None,
                average_mae_pct=None,
                average_peak_giveback_pct=None,
            )

        count = Decimal(len(diagnostics))

        return BacktestDiagnostics(
            trades=tuple(diagnostics),
            average_mfe_pct=(
                sum(
                    (trade.mfe_pct for trade in diagnostics),
                    Decimal("0"),
                )
                / count
            ),
            average_mae_pct=(
                sum(
                    (trade.mae_pct for trade in diagnostics),
                    Decimal("0"),
                )
                / count
            ),
            average_peak_giveback_pct=(
                sum(
                    (trade.peak_giveback_pct for trade in diagnostics),
                    Decimal("0"),
                )
                / count
            ),
        )
