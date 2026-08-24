from decimal import Decimal

import pytest

from alphapilot.strategy.ema20_pullback import (
    EMA20PullbackStrategy,
)
from alphapilot.strategy.evaluation import (
    SignalReason,
)
from alphapilot.strategy.exit_mode import (
    TrendExitMode,
)


def test_ema50_exit_waits_for_close_below_ema50() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.EMA50,
    )

    reason = strategy._get_exit_reason(
        close=Decimal("95"),
        ema20=Decimal("100"),
        ema50=Decimal("90"),
    )

    assert reason is None


def test_ema50_exit_sells_below_ema50() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.EMA50,
    )

    reason = strategy._get_exit_reason(
        close=Decimal("89"),
        ema20=Decimal("100"),
        ema50=Decimal("90"),
    )

    assert reason == SignalReason.TREND_BREAKDOWN


def test_ema20_exit_sells_below_ema20() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.EMA20,
    )

    reason = strategy._get_exit_reason(
        close=Decimal("95"),
        ema20=Decimal("100"),
        ema50=Decimal("90"),
    )

    assert reason == SignalReason.EMA20_TREND_BREAKDOWN


def test_ema20_exit_does_not_sell_above_ema20() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.EMA20,
    )

    reason = strategy._get_exit_reason(
        close=Decimal("101"),
        ema20=Decimal("100"),
        ema50=Decimal("90"),
    )

    assert reason is None


def test_hybrid_exits_on_ema20_when_trend_is_weak() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.HYBRID,
        hybrid_trend_threshold_pct=Decimal("3"),
    )

    reason = strategy._get_exit_reason(
        close=Decimal("99"),
        ema20=Decimal("100"),
        ema50=Decimal("98"),
    )

    assert reason == SignalReason.EMA20_TREND_BREAKDOWN


def test_hybrid_allows_ema20_break_in_strong_trend() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.HYBRID,
        hybrid_trend_threshold_pct=Decimal("3"),
    )

    reason = strategy._get_exit_reason(
        close=Decimal("104"),
        ema20=Decimal("110"),
        ema50=Decimal("100"),
    )

    assert reason is None


def test_hybrid_still_exits_below_ema50() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.HYBRID,
        hybrid_trend_threshold_pct=Decimal("3"),
    )

    reason = strategy._get_exit_reason(
        close=Decimal("99"),
        ema20=Decimal("110"),
        ema50=Decimal("100"),
    )

    assert reason == SignalReason.TREND_BREAKDOWN


def test_hybrid_threshold_boundary_counts_as_strong() -> None:
    strategy = EMA20PullbackStrategy(
        exit_mode=TrendExitMode.HYBRID,
        hybrid_trend_threshold_pct=Decimal("3"),
    )

    reason = strategy._get_exit_reason(
        close=Decimal("102"),
        ema20=Decimal("103"),
        ema50=Decimal("100"),
    )

    assert reason is None


def test_hybrid_threshold_must_not_be_negative() -> None:
    with pytest.raises(
        ValueError,
        match=("hybrid_trend_threshold_pct must not be negative"),
    ):
        EMA20PullbackStrategy(
            exit_mode=TrendExitMode.HYBRID,
            hybrid_trend_threshold_pct=Decimal("-1"),
        )
