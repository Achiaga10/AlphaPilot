from datetime import date
from decimal import Decimal

from alphapilot.backtesting.metrics import (
    PerformanceMetricsCalculator,
)
from alphapilot.backtesting.models import (
    BacktestTrade,
    TradeSimulationResult,
)


def create_trade(
    *,
    entry_price: str,
    exit_price: str,
) -> BacktestTrade:
    return BacktestTrade(
        entry_signal_day=date(
            2026,
            1,
            1,
        ),
        entry_day=date(
            2026,
            1,
            2,
        ),
        entry_price=Decimal(entry_price),
        exit_signal_day=date(
            2026,
            1,
            3,
        ),
        exit_day=date(
            2026,
            1,
            4,
        ),
        exit_price=Decimal(exit_price),
    )


def test_calculates_performance_metrics() -> None:
    simulation = TradeSimulationResult(
        ticker="AAPL",
        trades=(
            create_trade(
                entry_price="100",
                exit_price="110",
            ),
            create_trade(
                entry_price="100",
                exit_price="95",
            ),
            create_trade(
                entry_price="100",
                exit_price="120",
            ),
        ),
        open_position=None,
    )

    calculator = PerformanceMetricsCalculator()

    metrics = calculator.calculate(simulation)

    assert metrics.total_trades == 3

    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert metrics.breakeven_trades == 0

    expected_win_rate = Decimal("2") / Decimal("3") * Decimal("100")

    assert metrics.win_rate_pct == expected_win_rate

    expected_average = Decimal("25") / Decimal("3")

    assert metrics.average_return_pct == expected_average

    assert metrics.average_win_pct == Decimal("15")

    assert metrics.average_loss_pct == Decimal("-5")

    assert metrics.best_trade_pct == Decimal("20")

    assert metrics.worst_trade_pct == Decimal("-5")

    assert metrics.gross_profit_pct == Decimal("30")

    assert metrics.gross_loss_pct == Decimal("5")

    assert metrics.profit_factor == Decimal("6")

    assert metrics.compounded_return_pct == Decimal("25.4")


def test_empty_simulation_returns_zero_metrics() -> None:
    simulation = TradeSimulationResult(
        ticker="AAPL",
        trades=(),
        open_position=None,
    )

    calculator = PerformanceMetricsCalculator()

    metrics = calculator.calculate(simulation)

    assert metrics.total_trades == 0

    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 0
    assert metrics.breakeven_trades == 0

    assert metrics.win_rate_pct == Decimal("0")

    assert metrics.average_return_pct is None
    assert metrics.average_win_pct is None
    assert metrics.average_loss_pct is None

    assert metrics.best_trade_pct is None
    assert metrics.worst_trade_pct is None

    assert metrics.gross_profit_pct == Decimal("0")

    assert metrics.gross_loss_pct == Decimal("0")

    assert metrics.profit_factor is None

    assert metrics.compounded_return_pct == Decimal("0")


def test_profit_factor_is_none_when_there_are_no_losses() -> None:
    simulation = TradeSimulationResult(
        ticker="AAPL",
        trades=(
            create_trade(
                entry_price="100",
                exit_price="110",
            ),
            create_trade(
                entry_price="100",
                exit_price="120",
            ),
        ),
        open_position=None,
    )

    calculator = PerformanceMetricsCalculator()

    metrics = calculator.calculate(simulation)

    assert metrics.total_trades == 2
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 0

    assert metrics.gross_profit_pct == Decimal("30")

    assert metrics.gross_loss_pct == Decimal("0")

    assert metrics.profit_factor is None
