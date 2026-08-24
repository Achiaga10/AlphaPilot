from datetime import date
from decimal import Decimal

from alphapilot.backtesting.diagnostics import (
    BacktestDiagnostics,
    TradeDiagnostic,
)
from alphapilot.backtesting.entry_analysis import (
    EntryReasonPerformanceCalculator,
)
from alphapilot.strategy.evaluation import SignalReason


def create_diagnostic(
    *,
    return_pct: str,
    holding_days: int,
    mfe_pct: str,
    mae_pct: str,
    giveback_pct: str,
    reason: SignalReason,
) -> TradeDiagnostic:
    return TradeDiagnostic(
        entry_day=date(2026, 1, 1),
        exit_day=date(
            2026,
            1,
            1 + holding_days,
        ),
        entry_price=Decimal("100"),
        exit_price=(Decimal("100") * (Decimal("1") + Decimal(return_pct) / Decimal("100"))),
        return_pct=Decimal(return_pct),
        holding_days=holding_days,
        mfe_pct=Decimal(mfe_pct),
        mae_pct=Decimal(mae_pct),
        peak_giveback_pct=Decimal(giveback_pct),
        entry_reason=reason,
        exit_reason=(SignalReason.MICHO_150_BREAKDOWN),
    )


def test_calculates_breakout_trade_metrics() -> None:
    diagnostics = BacktestDiagnostics(
        trades=(
            create_diagnostic(
                return_pct="10",
                holding_days=10,
                mfe_pct="15",
                mae_pct="-2",
                giveback_pct="4",
                reason=(SignalReason.MICHO_150_BREAKOUT),
            ),
            create_diagnostic(
                return_pct="-5",
                holding_days=20,
                mfe_pct="5",
                mae_pct="-6",
                giveback_pct="7",
                reason=(SignalReason.MICHO_150_BREAKOUT),
            ),
            create_diagnostic(
                return_pct="20",
                holding_days=15,
                mfe_pct="25",
                mae_pct="-3",
                giveback_pct="5",
                reason=(SignalReason.MICHO_150_BOUNCE),
            ),
        ),
        average_mfe_pct=None,
        average_mae_pct=None,
        average_peak_giveback_pct=None,
    )

    calculator = EntryReasonPerformanceCalculator()

    result = calculator.calculate(
        diagnostics,
        reason=SignalReason.MICHO_150_BREAKOUT,
    )

    assert result.total_trades == 2
    assert result.winning_trades == 1
    assert result.losing_trades == 1
    assert result.breakeven_trades == 0

    assert result.win_rate_pct == Decimal("50")

    assert result.average_trade_pct == Decimal("2.5")

    assert result.average_win_pct == Decimal("10")

    assert result.average_loss_pct == Decimal("-5")

    assert result.profit_factor == Decimal("2")

    assert result.compounded_return_pct == Decimal("4.500")

    assert result.average_holding_days == Decimal("15")

    assert result.average_mfe_pct == Decimal("10")

    assert result.average_mae_pct == Decimal("-4")

    assert result.average_peak_giveback_pct == Decimal("5.5")


def test_calculates_only_requested_entry_reason() -> None:
    diagnostics = BacktestDiagnostics(
        trades=(
            create_diagnostic(
                return_pct="10",
                holding_days=10,
                mfe_pct="15",
                mae_pct="-2",
                giveback_pct="4",
                reason=(SignalReason.MICHO_150_BREAKOUT),
            ),
            create_diagnostic(
                return_pct="20",
                holding_days=20,
                mfe_pct="30",
                mae_pct="-1",
                giveback_pct="3",
                reason=(SignalReason.MICHO_150_BOUNCE),
            ),
        ),
        average_mfe_pct=None,
        average_mae_pct=None,
        average_peak_giveback_pct=None,
    )

    calculator = EntryReasonPerformanceCalculator()

    result = calculator.calculate(
        diagnostics,
        reason=SignalReason.MICHO_150_BOUNCE,
    )

    assert result.total_trades == 1

    assert result.average_trade_pct == Decimal("20")


def test_returns_empty_metrics_when_reason_has_no_trades() -> None:
    diagnostics = BacktestDiagnostics(
        trades=(),
        average_mfe_pct=None,
        average_mae_pct=None,
        average_peak_giveback_pct=None,
    )

    calculator = EntryReasonPerformanceCalculator()

    result = calculator.calculate(
        diagnostics,
        reason=SignalReason.MICHO_150_BREAKOUT,
    )

    assert result.total_trades == 0
    assert result.winning_trades == 0
    assert result.losing_trades == 0
    assert result.win_rate_pct is None
    assert result.average_trade_pct is None
    assert result.profit_factor is None
