from datetime import date
from decimal import Decimal

import pytest

from alphapilot.portfolio.exit_guidance import StrategyExitContext, StrategyExitState
from alphapilot.portfolio.monitoring import (
    MonitoringReason,
    MonitoringStatus,
    classify_monitoring,
)
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def context(
    strategy: StrategyName,
    state: StrategyExitState,
    *,
    close: str,
    sma150: str | None = None,
) -> StrategyExitContext:
    return StrategyExitContext(
        strategy=strategy,
        data_as_of_date=date(2026, 8, 27),
        reference_close=Decimal(close),
        current_signal=Signal.HOLD,
        signal_reason="test",
        exit_mode="frozen",
        current_exit_state=state,
        sma150=Decimal(sma150) if sma150 else None,
    )


@pytest.mark.parametrize(
    ("state", "status", "reason"),
    [
        (StrategyExitState.ABOVE_EMA20, MonitoringStatus.HOLD, MonitoringReason.EMA20_HELD),
        (
            StrategyExitState.BELOW_EMA20_STRONG_TREND,
            MonitoringStatus.ATTENTION,
            MonitoringReason.EMA20_LOST_STRONG_TREND_HOLD,
        ),
        (
            StrategyExitState.EMA20_WEAK_TREND_BREAKDOWN,
            MonitoringStatus.SELL,
            MonitoringReason.EMA20_WEAK_TREND_BREAKDOWN,
        ),
        (
            StrategyExitState.EMA50_BREAKDOWN,
            MonitoringStatus.SELL,
            MonitoringReason.EMA50_BREAKDOWN,
        ),
    ],
)
def test_ema_monitoring_reuses_frozen_exit_states(
    state: StrategyExitState, status: MonitoringStatus, reason: MonitoringReason
) -> None:
    assert classify_monitoring(
        strategy=StrategyName.EMA20_PULLBACK,
        context=context(StrategyName.EMA20_PULLBACK, state, close="100"),
        latest_low=Decimal("99"),
    ) == (status, reason)


@pytest.mark.parametrize(
    ("close", "low", "status", "reason"),
    [
        ("101", "100", MonitoringStatus.HOLD, MonitoringReason.SMA150_HELD),
        (
            "101",
            "99",
            MonitoringStatus.ATTENTION,
            MonitoringReason.SMA150_INTRADAY_BREACH_RECOVERED,
        ),
        (
            "100",
            "99",
            MonitoringStatus.ATTENTION,
            MonitoringReason.SMA150_CLOSE_AT_SUPPORT,
        ),
        ("99", "98", MonitoringStatus.SELL, MonitoringReason.SMA150_BREAKDOWN),
    ],
)
def test_micho_monitoring_uses_ohlc_without_distance_threshold(
    close: str,
    low: str,
    status: MonitoringStatus,
    reason: MonitoringReason,
) -> None:
    state = (
        StrategyExitState.SMA150_BREAKDOWN
        if Decimal(close) < Decimal("100")
        else StrategyExitState.ABOVE_SMA150
    )
    assert classify_monitoring(
        strategy=StrategyName.MICHO_150,
        context=context(StrategyName.MICHO_150, state, close=close, sma150="100"),
        latest_low=Decimal(low),
    ) == (status, reason)
