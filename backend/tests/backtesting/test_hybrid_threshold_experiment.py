from decimal import Decimal

from alphapilot.backtesting.hybrid_threshold_experiment import (
    HybridThresholdAggregate,
    select_threshold,
)


def create_aggregate(
    threshold: str,
    *,
    sharpe: str,
    drawdown: str,
    total_return: str,
) -> HybridThresholdAggregate:
    return HybridThresholdAggregate(
        threshold_pct=Decimal(threshold),
        successful=500,
        failed=0,
        profitable_count=250,
        beats_spy_count=50,
        beats_stock_count=100,
        median_total_return_pct=Decimal(total_return),
        median_cagr_pct=Decimal("1"),
        median_max_drawdown_pct=Decimal(drawdown),
        median_sharpe_ratio=Decimal(sharpe),
        median_profit_factor=Decimal("1"),
        median_peak_giveback_pct=Decimal("5"),
    )


def test_selection_prefers_highest_median_sharpe() -> None:
    aggregates = [
        create_aggregate(
            "1",
            sharpe="0.20",
            drawdown="20",
            total_return="10",
        ),
        create_aggregate(
            "2",
            sharpe="0.30",
            drawdown="30",
            total_return="5",
        ),
    ]

    selected = select_threshold(aggregates)

    assert selected.threshold_pct == Decimal("2")


def test_selection_uses_lower_drawdown_as_tiebreaker() -> None:
    aggregates = [
        create_aggregate(
            "1",
            sharpe="0.30",
            drawdown="20",
            total_return="5",
        ),
        create_aggregate(
            "2",
            sharpe="0.30",
            drawdown="15",
            total_return="4",
        ),
    ]

    selected = select_threshold(aggregates)

    assert selected.threshold_pct == Decimal("2")


def test_selection_uses_return_as_final_tiebreaker() -> None:
    aggregates = [
        create_aggregate(
            "1",
            sharpe="0.30",
            drawdown="15",
            total_return="8",
        ),
        create_aggregate(
            "2",
            sharpe="0.30",
            drawdown="15",
            total_return="10",
        ),
    ]

    selected = select_threshold(aggregates)

    assert selected.threshold_pct == Decimal("2")
