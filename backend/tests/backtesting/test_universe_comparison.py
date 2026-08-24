from datetime import date
from decimal import Decimal

from alphapilot.backtesting.universe_comparison import (
    UniverseExitComparisonRow,
    build_universe_summary,
)


def test_summary_compares_exit_modes() -> None:
    rows = [
        UniverseExitComparisonRow(
            ticker="AAA",
            ema50_total_return_pct=Decimal("10"),
            ema20_total_return_pct=Decimal("20"),
            ema50_cagr_pct=Decimal("5"),
            ema20_cagr_pct=Decimal("8"),
            ema50_max_drawdown_pct=Decimal("20"),
            ema20_max_drawdown_pct=Decimal("10"),
            ema50_sharpe_ratio=Decimal("0.5"),
            ema20_sharpe_ratio=Decimal("0.8"),
            ema50_profit_factor=Decimal("1.5"),
            ema20_profit_factor=Decimal("2"),
            ema50_peak_giveback_pct=Decimal("8"),
            ema20_peak_giveback_pct=Decimal("4"),
            stock_buy_hold_return_pct=Decimal("15"),
            spy_buy_hold_return_pct=Decimal("12"),
        ),
        UniverseExitComparisonRow(
            ticker="BBB",
            ema50_total_return_pct=Decimal("30"),
            ema20_total_return_pct=Decimal("20"),
            ema50_cagr_pct=Decimal("10"),
            ema20_cagr_pct=Decimal("8"),
            ema50_max_drawdown_pct=Decimal("15"),
            ema20_max_drawdown_pct=Decimal("20"),
            ema50_sharpe_ratio=Decimal("1"),
            ema20_sharpe_ratio=Decimal("0.7"),
            ema50_profit_factor=Decimal("2"),
            ema20_profit_factor=Decimal("1.5"),
            ema50_peak_giveback_pct=Decimal("5"),
            ema20_peak_giveback_pct=Decimal("7"),
            stock_buy_hold_return_pct=Decimal("25"),
            spy_buy_hold_return_pct=Decimal("12"),
        ),
    ]

    summary = build_universe_summary(
        rows,
        start=date(2021, 8, 20),
        end=date(2026, 8, 20),
    )

    assert "Successful: 2" in summary

    assert "Total return: EMA20=1, EMA50=1, Ties=0" in summary

    assert "EMA20 beats SPY: 2/2" in summary
    assert "EMA50 beats SPY: 1/2" in summary

    assert "survivorship bias" in summary
