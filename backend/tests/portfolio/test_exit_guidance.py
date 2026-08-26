from datetime import date
from decimal import Decimal

from alphapilot.portfolio.exit_guidance import (
    FixedTakeProfitPolicy,
    StrategyExitState,
    build_strategy_exit_context,
)
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def test_ema_hybrid_exit_context_matches_frozen_strategy_branches() -> None:
    evaluation = StrategyEvaluation(
        Signal.HOLD,
        SignalReason.NO_PULLBACK,
        ema20=Decimal("105"),
        ema50=Decimal("100"),
    )
    context = build_strategy_exit_context(
        strategy=StrategyName.EMA20_PULLBACK,
        evaluation=evaluation,
        data_as_of_date=date(2026, 8, 20),
        reference_close=Decimal("103"),
        exit_mode=TrendExitMode.HYBRID,
        hybrid_threshold_pct=Decimal("2"),
    )
    assert context.current_exit_state == StrategyExitState.BELOW_EMA20_STRONG_TREND
    assert context.ema_spread_pct == Decimal("5.00")
    assert context.distance_to_ema50_pct == Decimal("3.00")
    assert context.hybrid_threshold_pct == Decimal("2")
    assert context.fixed_take_profit_policy == FixedTakeProfitPolicy.NONE

    hard_exit = build_strategy_exit_context(
        strategy=StrategyName.EMA20_PULLBACK,
        evaluation=StrategyEvaluation(
            Signal.SELL,
            SignalReason.TREND_BREAKDOWN,
            ema20=Decimal("105"),
            ema50=Decimal("100"),
        ),
        data_as_of_date=date(2026, 8, 20),
        reference_close=Decimal("99"),
        exit_mode=TrendExitMode.HYBRID,
        hybrid_threshold_pct=Decimal("2"),
    )
    assert hard_exit.current_exit_state == StrategyExitState.EMA50_BREAKDOWN


def test_micho_exit_context_uses_close_below_sma150_only() -> None:
    context = build_strategy_exit_context(
        strategy=StrategyName.MICHO_150,
        evaluation=StrategyEvaluation(
            Signal.SELL,
            SignalReason.MICHO_150_BREAKDOWN,
            sma150=Decimal("100"),
        ),
        data_as_of_date=date(2026, 8, 20),
        reference_close=Decimal("98"),
        exit_mode=TrendExitMode.HYBRID,
        hybrid_threshold_pct=Decimal("2"),
    )
    assert context.exit_mode == "close-below-sma150"
    assert context.current_exit_state == StrategyExitState.SMA150_BREAKDOWN
    assert context.distance_to_sma150_pct == Decimal("-2.00")
    assert context.fixed_take_profit_policy == FixedTakeProfitPolicy.NONE
