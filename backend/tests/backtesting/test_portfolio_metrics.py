from datetime import date
from decimal import Decimal

from alphapilot.backtesting.models import (
    EquityCurvePoint,
    PortfolioSimulationResult,
    PortfolioTrade,
)
from alphapilot.backtesting.portfolio_metrics import (
    PortfolioPerformanceMetricsCalculator,
)


def create_equity_point(
    trading_day: date,
    *,
    equity: str,
    shares: int,
) -> EquityCurvePoint:
    equity_value = Decimal(equity)

    return EquityCurvePoint(
        trading_day=trading_day,
        cash=equity_value,
        shares=shares,
        market_price=Decimal("0"),
        equity=equity_value,
    )


def create_trade() -> PortfolioTrade:
    return PortfolioTrade(
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
        entry_price=Decimal("100"),
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
        exit_price=Decimal("110"),
        shares=10,
        entry_commission=Decimal("0"),
        exit_commission=Decimal("0"),
    )


def test_calculates_portfolio_metrics() -> None:
    portfolio = PortfolioSimulationResult(
        ticker="AAPL",
        initial_capital=Decimal("100"),
        final_equity=Decimal("110"),
        equity_curve=(
            create_equity_point(
                date(2026, 1, 1),
                equity="100",
                shares=0,
            ),
            create_equity_point(
                date(2026, 1, 2),
                equity="120",
                shares=10,
            ),
            create_equity_point(
                date(2026, 1, 3),
                equity="90",
                shares=10,
            ),
            create_equity_point(
                date(2026, 1, 4),
                equity="110",
                shares=0,
            ),
        ),
        trades=(create_trade(),),
        open_position=None,
    )

    calculator = PortfolioPerformanceMetricsCalculator()

    metrics = calculator.calculate(portfolio)

    assert metrics.final_equity == Decimal("110")

    assert metrics.total_return_pct == Decimal("10")

    assert metrics.max_drawdown_pct == Decimal("25")

    assert metrics.exposure_pct == Decimal("50")

    assert metrics.completed_trades == 1

    assert metrics.average_holding_days == Decimal("2")

    assert metrics.cagr_pct is not None
    assert metrics.sharpe_ratio is not None


def test_empty_portfolio_metrics() -> None:
    portfolio = PortfolioSimulationResult(
        ticker="AAPL",
        initial_capital=Decimal("100000"),
        final_equity=Decimal("100000"),
        equity_curve=(),
        trades=(),
        open_position=None,
    )

    calculator = PortfolioPerformanceMetricsCalculator()

    metrics = calculator.calculate(portfolio)

    assert metrics.total_return_pct == Decimal("0")

    assert metrics.max_drawdown_pct == Decimal("0")

    assert metrics.exposure_pct == Decimal("0")

    assert metrics.cagr_pct is None
    assert metrics.sharpe_ratio is None

    assert metrics.average_holding_days is None


def test_flat_equity_has_no_sharpe_ratio() -> None:
    portfolio = PortfolioSimulationResult(
        ticker="AAPL",
        initial_capital=Decimal("100"),
        final_equity=Decimal("100"),
        equity_curve=(
            create_equity_point(
                date(2026, 1, 1),
                equity="100",
                shares=0,
            ),
            create_equity_point(
                date(2026, 1, 2),
                equity="100",
                shares=0,
            ),
            create_equity_point(
                date(2026, 1, 3),
                equity="100",
                shares=0,
            ),
        ),
        trades=(),
        open_position=None,
    )

    calculator = PortfolioPerformanceMetricsCalculator()

    metrics = calculator.calculate(portfolio)

    assert metrics.max_drawdown_pct == Decimal("0")

    assert metrics.sharpe_ratio is None
