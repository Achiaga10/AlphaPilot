from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from alphapilot.strategy.evaluation import StrategyEvaluation
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


class StrategyExitState(StrEnum):
    ABOVE_EMA20 = "ABOVE_EMA20"
    BELOW_EMA20_STRONG_TREND = "BELOW_EMA20_STRONG_TREND"
    EMA20_WEAK_TREND_BREAKDOWN = "EMA20_WEAK_TREND_BREAKDOWN"
    EMA50_BREAKDOWN = "EMA50_BREAKDOWN"
    ABOVE_SMA150 = "ABOVE_SMA150"
    SMA150_BREAKDOWN = "SMA150_BREAKDOWN"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class FixedTakeProfitPolicy(StrEnum):
    NONE = "NONE"


@dataclass(slots=True, frozen=True)
class StrategyExitContext:
    strategy: StrategyName
    data_as_of_date: date
    reference_close: Decimal
    current_signal: Signal
    signal_reason: str
    exit_mode: str
    current_exit_state: StrategyExitState
    fixed_take_profit_policy: FixedTakeProfitPolicy = FixedTakeProfitPolicy.NONE
    ema20: Decimal | None = None
    ema50: Decimal | None = None
    ema_spread_pct: Decimal | None = None
    hybrid_threshold_pct: Decimal | None = None
    distance_to_ema20_pct: Decimal | None = None
    distance_to_ema50_pct: Decimal | None = None
    sma150: Decimal | None = None
    distance_to_sma150_pct: Decimal | None = None


def build_strategy_exit_context(
    *,
    strategy: StrategyName,
    evaluation: StrategyEvaluation,
    data_as_of_date: date,
    reference_close: Decimal,
    exit_mode: TrendExitMode,
    hybrid_threshold_pct: Decimal,
) -> StrategyExitContext:
    if strategy == StrategyName.MICHO_150:
        sma150 = evaluation.sma150
        state = (
            StrategyExitState.INSUFFICIENT_HISTORY
            if sma150 is None
            else (
                StrategyExitState.SMA150_BREAKDOWN
                if reference_close < sma150
                else StrategyExitState.ABOVE_SMA150
            )
        )
        return StrategyExitContext(
            strategy=strategy,
            data_as_of_date=data_as_of_date,
            reference_close=reference_close,
            current_signal=evaluation.signal,
            signal_reason=evaluation.reason.value,
            exit_mode="close-below-sma150",
            current_exit_state=state,
            sma150=sma150,
            distance_to_sma150_pct=_distance_pct(reference_close, sma150),
        )

    ema20 = evaluation.ema20
    ema50 = evaluation.ema50
    spread = _distance_pct(ema20, ema50)
    if ema20 is None or ema50 is None:
        state = StrategyExitState.INSUFFICIENT_HISTORY
    elif reference_close < ema50:
        state = StrategyExitState.EMA50_BREAKDOWN
    elif reference_close >= ema20:
        state = StrategyExitState.ABOVE_EMA20
    elif spread is not None and spread >= hybrid_threshold_pct:
        state = StrategyExitState.BELOW_EMA20_STRONG_TREND
    else:
        state = StrategyExitState.EMA20_WEAK_TREND_BREAKDOWN
    return StrategyExitContext(
        strategy=strategy,
        data_as_of_date=data_as_of_date,
        reference_close=reference_close,
        current_signal=evaluation.signal,
        signal_reason=evaluation.reason.value,
        exit_mode=(
            f"{exit_mode.value}-{hybrid_threshold_pct}%"
            if exit_mode == TrendExitMode.HYBRID
            else exit_mode.value
        ),
        current_exit_state=state,
        ema20=ema20,
        ema50=ema50,
        ema_spread_pct=spread,
        hybrid_threshold_pct=(hybrid_threshold_pct if exit_mode == TrendExitMode.HYBRID else None),
        distance_to_ema20_pct=_distance_pct(reference_close, ema20),
        distance_to_ema50_pct=_distance_pct(reference_close, ema50),
    )


def _distance_pct(value: Decimal | None, reference: Decimal | None) -> Decimal | None:
    if value is None or reference is None or reference <= 0:
        return None
    return (value - reference) / reference * Decimal("100")
