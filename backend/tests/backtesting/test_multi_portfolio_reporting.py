from datetime import date
from decimal import Decimal

from alphapilot.backtesting.models import PortfolioSimulationResult
from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetrics,
)
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioConfig,
    MultiPortfolioEquityPoint,
    MultiPortfolioSimulationResult,
)
from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioRunResult
from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.backtesting.portfolio_metrics import PortfolioPerformanceMetrics
from alphapilot.cli.backtest_multi_portfolio import build_summary
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName


def test_summary_documents_research_configuration_and_limitations() -> None:
    point = MultiPortfolioEquityPoint(
        trading_day=date(2025, 1, 2),
        cash=Decimal("100000"),
        invested_value=Decimal("0"),
        equity=Decimal("100000"),
        open_positions=0,
    )
    portfolio = MultiPortfolioSimulationResult(
        initial_capital=Decimal("100000"),
        final_equity=Decimal("100000"),
        equity_curve=(point,),
        trades=(),
        open_positions=(),
    )
    metrics = MultiPortfolioPerformanceMetrics(
        initial_equity=Decimal("100000"),
        final_equity=Decimal("100000"),
        total_return_pct=Decimal("0"),
        cagr_pct=None,
        max_drawdown_pct=Decimal("0"),
        sharpe_ratio=None,
        exposure_pct=Decimal("0"),
        completed_trades=0,
        win_rate_pct=Decimal("0"),
        profit_factor=None,
        average_trade_pct=None,
        turnover_pct=Decimal("0"),
        average_open_positions=Decimal("0"),
        max_concurrent_positions=0,
    )
    spy = PortfolioSimulationResult(
        ticker="SPY",
        initial_capital=Decimal("100000"),
        final_equity=Decimal("100000"),
        equity_curve=(),
        trades=(),
        open_position=None,
    )
    spy_metrics = PortfolioPerformanceMetrics(
        final_equity=Decimal("100000"),
        total_return_pct=Decimal("0"),
        cagr_pct=None,
        max_drawdown_pct=Decimal("0"),
        sharpe_ratio=None,
        exposure_pct=Decimal("0"),
        completed_trades=0,
        average_holding_days=None,
    )
    result = MultiPortfolioRunResult(
        portfolio=portfolio,
        metrics=metrics,
        spy_buy_and_hold=spy,
        spy_metrics=spy_metrics,
        successful_tickers=("AAA",),
        failed_tickers=(),
        selection_policy_name="ticker-ascending-baseline",
        attribution=PortfolioAttributionCalculator().calculate(portfolio),
    )

    summary = build_summary(
        result,
        strategy_name=StrategyName.EMA20_PULLBACK,
        exit_mode=TrendExitMode.HYBRID,
        hybrid_threshold=Decimal("2"),
        micho_entry_mode=MichoEntryMode.BOTH,
        start=date(2025, 1, 1),
        end=date(2026, 8, 20),
        config=MultiPortfolioConfig(),
        cost_scenario="cost-low",
        fold_label="fold-3",
    )

    assert "Hybrid trend threshold: 2.00%" in summary
    assert "Max positions: 10" in summary
    assert "fixed equal slot" in summary
    assert "ticker-ascending-baseline" in summary
    assert "non-alpha" in summary
    assert "marked to market" in summary
    assert "survivorship bias" in summary
    assert "Benchmark caveat" in summary
    assert "Cost scenario: cost-low" in summary
    assert "Temporal fold: fold-3" in summary
    assert "Reconciliation residual" in summary
