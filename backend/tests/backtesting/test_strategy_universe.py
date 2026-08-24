from datetime import date
from decimal import Decimal

from alphapilot.backtesting.strategy_universe import (
    StrategyUniverseRow,
    build_strategy_universe_summary,
)
from alphapilot.strategy.name import StrategyName


def test_micho_summary_includes_executed_entry_analysis() -> None:
    rows = [
        StrategyUniverseRow(
            ticker="AAA",
            strategy="micho-150",
            executed_trades=4,
            breakout_buy_signals=5,
            bounce_buy_signals=10,
            breakout_completed_trades=3,
            breakout_win_rate_pct=Decimal("50"),
            breakout_average_trade_pct=Decimal("2"),
            breakout_average_win_pct=Decimal("8"),
            breakout_average_loss_pct=Decimal("-3"),
            breakout_profit_factor=Decimal("2"),
            breakout_compounded_return_pct=Decimal("6"),
            breakout_average_holding_days=Decimal("10"),
            breakout_average_mfe_pct=Decimal("7"),
            breakout_average_mae_pct=Decimal("-2"),
            breakout_peak_giveback_pct=Decimal("4"),
            bounce_completed_trades=1,
            bounce_win_rate_pct=Decimal("25"),
            bounce_average_trade_pct=Decimal("-1"),
            bounce_average_win_pct=Decimal("5"),
            bounce_average_loss_pct=Decimal("-3"),
            bounce_profit_factor=Decimal("0.5"),
            bounce_compounded_return_pct=Decimal("-1"),
            bounce_average_holding_days=Decimal("20"),
            bounce_average_mfe_pct=Decimal("8"),
            bounce_average_mae_pct=Decimal("-4"),
            bounce_peak_giveback_pct=Decimal("7"),
            total_return_pct=Decimal("10"),
            cagr_pct=Decimal("5"),
            max_drawdown_pct=Decimal("12"),
            sharpe_ratio=Decimal("0.5"),
            profit_factor=Decimal("1.5"),
            win_rate_pct=Decimal("40"),
            completed_trades=4,
            exposure_pct=Decimal("30"),
            average_holding_days=Decimal("15"),
            average_mfe_pct=Decimal("7"),
            average_mae_pct=Decimal("-3"),
            peak_giveback_pct=Decimal("5"),
            stock_buy_hold_return_pct=Decimal("8"),
            spy_buy_hold_return_pct=Decimal("7"),
        ),
        StrategyUniverseRow(
            ticker="BBB",
            strategy="micho-150",
            executed_trades=3,
            breakout_buy_signals=4,
            bounce_buy_signals=8,
            breakout_completed_trades=1,
            breakout_win_rate_pct=Decimal("20"),
            breakout_average_trade_pct=Decimal("-2"),
            breakout_average_win_pct=Decimal("4"),
            breakout_average_loss_pct=Decimal("-4"),
            breakout_profit_factor=Decimal("0.4"),
            breakout_compounded_return_pct=Decimal("-2"),
            breakout_average_holding_days=Decimal("12"),
            breakout_average_mfe_pct=Decimal("5"),
            breakout_average_mae_pct=Decimal("-4"),
            breakout_peak_giveback_pct=Decimal("6"),
            bounce_completed_trades=2,
            bounce_win_rate_pct=Decimal("40"),
            bounce_average_trade_pct=Decimal("3"),
            bounce_average_win_pct=Decimal("9"),
            bounce_average_loss_pct=Decimal("-2"),
            bounce_profit_factor=Decimal("2.5"),
            bounce_compounded_return_pct=Decimal("7"),
            bounce_average_holding_days=Decimal("18"),
            bounce_average_mfe_pct=Decimal("10"),
            bounce_average_mae_pct=Decimal("-2"),
            bounce_peak_giveback_pct=Decimal("5"),
            total_return_pct=Decimal("5"),
            cagr_pct=Decimal("2"),
            max_drawdown_pct=Decimal("15"),
            sharpe_ratio=Decimal("0.3"),
            profit_factor=Decimal("1.2"),
            win_rate_pct=Decimal("35"),
            completed_trades=3,
            exposure_pct=Decimal("25"),
            average_holding_days=Decimal("14"),
            average_mfe_pct=Decimal("6"),
            average_mae_pct=Decimal("-3"),
            peak_giveback_pct=Decimal("5"),
            stock_buy_hold_return_pct=Decimal("6"),
            spy_buy_hold_return_pct=Decimal("7"),
        ),
    ]

    summary = build_strategy_universe_summary(
        rows,
        strategy_name=StrategyName.MICHO_150,
        start=date(2025, 1, 1),
        end=date(2026, 8, 20),
    )

    assert "MICHO EXECUTED ENTRY ANALYSIS" in summary
    assert "Total completed trades: 7" in summary
    assert "Classified completed trades: 7" in summary
    assert "Unclassified completed trades: 0" in summary

    assert "Completed trades: 4" in summary
    assert "Completed trades: 3" in summary

    assert "Stocks compared: 2" in summary
    assert "Breakout higher average trade: 1" in summary
    assert "Bounce higher average trade: 1" in summary
    assert "Ties: 0" in summary
