from datetime import date
from decimal import Decimal

from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioEquityPoint,
    MultiPortfolioSimulationResult,
    MultiPortfolioTrade,
)


def test_calculates_multi_portfolio_metrics() -> None:
    trade = MultiPortfolioTrade(
        ticker="AAA",
        entry_signal_day=date(2025, 1, 1),
        entry_day=date(2025, 1, 2),
        entry_price=Decimal("100"),
        exit_signal_day=date(2025, 1, 3),
        exit_day=date(2025, 1, 4),
        exit_price=Decimal("110"),
        shares=5,
        entry_commission=Decimal("0"),
        exit_commission=Decimal("0"),
        entry_reason=None,
        exit_reason=None,
    )
    result = MultiPortfolioSimulationResult(
        initial_capital=Decimal("1000"),
        final_equity=Decimal("1050"),
        equity_curve=(
            MultiPortfolioEquityPoint(
                date(2025, 1, 2), Decimal("500"), Decimal("500"), Decimal("1000"), 1
            ),
            MultiPortfolioEquityPoint(
                date(2025, 1, 3), Decimal("500"), Decimal("450"), Decimal("950"), 1
            ),
            MultiPortfolioEquityPoint(
                date(2026, 1, 2), Decimal("1050"), Decimal("0"), Decimal("1050"), 0
            ),
        ),
        trades=(trade,),
        open_positions=(),
    )

    metrics = MultiPortfolioPerformanceMetricsCalculator().calculate(result)

    assert metrics.initial_equity == Decimal("1000")
    assert metrics.final_equity == Decimal("1050")
    assert metrics.total_return_pct == Decimal("5.00")
    assert metrics.max_drawdown_pct == Decimal("5.00")
    assert metrics.completed_trades == 1
    assert metrics.win_rate_pct == Decimal("100")
    assert metrics.profit_factor is None
    assert metrics.average_trade_pct == Decimal("10")
    assert metrics.turnover_pct == Decimal("105")
    assert metrics.average_open_positions == Decimal("2") / Decimal("3")
    assert metrics.max_concurrent_positions == 1
