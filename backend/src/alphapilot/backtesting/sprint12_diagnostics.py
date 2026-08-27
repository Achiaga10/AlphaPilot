from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from alphapilot.backtesting.candidate_selection import CandidateSelectionPolicy
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetrics,
    MultiPortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import PreparedMultiPortfolioData


@dataclass(slots=True, frozen=True)
class UniverseExitComparison:
    ticker: str
    reference_configuration: str
    candidate_configuration: str
    reference_return_pct: Decimal
    candidate_return_pct: Decimal
    return_difference_pct: Decimal
    reference_max_drawdown_pct: Decimal
    candidate_max_drawdown_pct: Decimal
    drawdown_difference_pct: Decimal
    candidate_median_mae_pct: Decimal | None
    candidate_median_mfe_pct: Decimal | None
    candidate_stop_count: int
    candidate_gap_stop_count: int
    candidate_completed_trades: int
    candidate_beats_reference: bool


def calculate_universe_exit_comparisons(
    *,
    prepared: PreparedMultiPortfolioData,
    selection_policy: CandidateSelectionPolicy,
    configurations: tuple[tuple[str, MultiPortfolioConfig], ...],
) -> tuple[UniverseExitComparison, ...]:
    """Independent single-ticker diagnostics; not used to select portfolio trades."""

    if len(configurations) < 2:
        return ()
    calculator = MultiPortfolioPerformanceMetricsCalculator()
    rows: list[UniverseExitComparison] = []
    for ticker in sorted(prepared.backtests):
        results: dict[str, MultiPortfolioPerformanceMetrics] = {}
        stop_counts: dict[str, tuple[int, int]] = {}
        for label, config in configurations:
            portfolio = MultiPortfolioSimulator(
                config=config,
                selection_policy=selection_policy,
            ).run(
                {ticker: prepared.backtests[ticker]},
                ranking_scores={
                    key: value for key, value in prepared.ranking_scores.items() if key[0] == ticker
                },
                ticker_sectors={ticker: prepared.ticker_sectors.get(ticker)},
                atr_values={
                    key: value for key, value in prepared.atr_values.items() if key[0] == ticker
                },
            )
            results[label] = calculator.calculate(portfolio)
            stop_counts[label] = (
                portfolio.trade_management_diagnostics.stop_hit_count,
                portfolio.trade_management_diagnostics.gap_through_stop_count,
            )
        reference_label, _ = configurations[0]
        reference = results[reference_label]
        for candidate_label, _ in configurations[1:]:
            candidate = results[candidate_label]
            rows.append(
                UniverseExitComparison(
                    ticker=ticker,
                    reference_configuration=reference_label,
                    candidate_configuration=candidate_label,
                    reference_return_pct=reference.total_return_pct,
                    candidate_return_pct=candidate.total_return_pct,
                    return_difference_pct=(candidate.total_return_pct - reference.total_return_pct),
                    reference_max_drawdown_pct=reference.max_drawdown_pct,
                    candidate_max_drawdown_pct=candidate.max_drawdown_pct,
                    drawdown_difference_pct=(
                        candidate.max_drawdown_pct - reference.max_drawdown_pct
                    ),
                    candidate_median_mae_pct=candidate.median_mae_pct,
                    candidate_median_mfe_pct=candidate.median_mfe_pct,
                    candidate_stop_count=stop_counts[candidate_label][0],
                    candidate_gap_stop_count=stop_counts[candidate_label][1],
                    candidate_completed_trades=candidate.completed_trades,
                    candidate_beats_reference=(
                        candidate.total_return_pct > reference.total_return_pct
                    ),
                )
            )
    return tuple(rows)


def write_universe_exit_comparisons(
    path: Path,
    rows: tuple[UniverseExitComparison, ...],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(UniverseExitComparison.__dataclass_fields__)
        writer.writerows(
            tuple(getattr(row, field) for field in UniverseExitComparison.__dataclass_fields__)
            for row in rows
        )
