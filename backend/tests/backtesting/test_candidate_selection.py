from datetime import date
from decimal import Decimal

from alphapilot.backtesting.candidate_selection import (
    ExecutableCandidate,
    RelativeStrength20SelectionPolicy,
    TickerAscendingSelectionPolicy,
)
from alphapilot.backtesting.models import BacktestBarResult
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal


def candidate(ticker: str, score: str | None) -> ExecutableCandidate:
    evaluation = StrategyEvaluation(
        signal=Signal.BUY,
        reason=SignalReason.EMA20_PULLBACK_RECLAIM,
    )
    signal_bar = BacktestBarResult(
        trading_day=date(2025, 1, 2),
        open=Decimal("100"),
        close=Decimal("100"),
        evaluation=evaluation,
    )
    execution_bar = BacktestBarResult(
        trading_day=date(2025, 1, 3),
        open=Decimal("100"),
        close=Decimal("100"),
        evaluation=evaluation,
    )
    return ExecutableCandidate(
        ticker=ticker,
        signal_bar=signal_bar,
        execution_bar=execution_bar,
        ranking_score=Decimal(score) if score is not None else None,
    )


def test_rs20_orders_highest_score_first_including_negative_values() -> None:
    ordered = RelativeStrength20SelectionPolicy().order(
        [candidate("LOW", "-0.2"), candidate("HIGH", "0.1"), candidate("MID", "-0.1")]
    )

    assert [item.ticker for item in ordered] == ["HIGH", "MID", "LOW"]


def test_rs20_tie_breaks_by_ticker() -> None:
    ordered = RelativeStrength20SelectionPolicy().order(
        [candidate("BBB", "0.1"), candidate("AAA", "0.1")]
    )

    assert [item.ticker for item in ordered] == ["AAA", "BBB"]


def test_scored_candidates_precede_unscored_then_ticker_fallback() -> None:
    ordered = RelativeStrength20SelectionPolicy().order(
        [candidate("AAA", None), candidate("ZZZ", "-1"), candidate("BBB", None)]
    )

    assert [item.ticker for item in ordered] == ["ZZZ", "AAA", "BBB"]
    assert ordered[1].ranking_score is None
    assert ordered[2].ranking_score is None


def test_ticker_ascending_control_remains_score_independent() -> None:
    ordered = TickerAscendingSelectionPolicy().order(
        [candidate("BBB", "10"), candidate("AAA", "-10")]
    )

    assert [item.ticker for item in ordered] == ["AAA", "BBB"]
