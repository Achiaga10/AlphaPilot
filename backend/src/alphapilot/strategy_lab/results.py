from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioRunResult
from alphapilot.strategy_lab.models import StrategyLabResultSummary


def summarize_portfolio_result(result: MultiPortfolioRunResult) -> StrategyLabResultSummary:
    metrics = result.metrics
    attribution = result.attribution
    return StrategyLabResultSummary(
        final_equity=metrics.final_equity,
        total_return_pct=metrics.total_return_pct,
        cagr_pct=metrics.cagr_pct,
        max_drawdown_pct=metrics.max_drawdown_pct,
        sharpe_ratio=metrics.sharpe_ratio,
        calmar_ratio=metrics.calmar_ratio,
        profit_factor=metrics.profit_factor,
        win_rate_pct=metrics.win_rate_pct,
        completed_trades=metrics.completed_trades,
        exposure_pct=metrics.exposure_pct,
        turnover_pct=metrics.turnover_pct,
        realized_pnl=attribution.realized_pnl,
        unrealized_pnl=attribution.unrealized_pnl,
        top_5_positive_pnl_share_pct=attribution.top_5_positive_pnl_share_pct,
    )
