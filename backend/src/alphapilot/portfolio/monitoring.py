from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from alphapilot.portfolio.exit_guidance import StrategyExitContext, StrategyExitState
from alphapilot.strategy.name import StrategyName


class MonitoringReadiness(StrEnum):
    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"


class MonitoringStatus(StrEnum):
    HOLD = "HOLD"
    ATTENTION = "ATTENTION"
    SELL = "SELL"


class MonitoringReason(StrEnum):
    EMA20_HELD = "EMA20_HELD"
    EMA20_LOST_STRONG_TREND_HOLD = "EMA20_LOST_STRONG_TREND_HOLD"
    EMA20_WEAK_TREND_BREAKDOWN = "EMA20_WEAK_TREND_BREAKDOWN"
    EMA50_BREAKDOWN = "EMA50_BREAKDOWN"
    SMA150_HELD = "SMA150_HELD"
    SMA150_INTRADAY_BREACH_RECOVERED = "SMA150_INTRADAY_BREACH_RECOVERED"
    SMA150_CLOSE_AT_SUPPORT = "SMA150_CLOSE_AT_SUPPORT"
    SMA150_BREAKDOWN = "SMA150_BREAKDOWN"
    STRATEGY_PROFILE_UNKNOWN = "STRATEGY_PROFILE_UNKNOWN"
    UNSUPPORTED_PROFILE_VERSION = "UNSUPPORTED_PROFILE_VERSION"
    MARKET_DATA_UNAVAILABLE = "MARKET_DATA_UNAVAILABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


@dataclass(slots=True, frozen=True)
class PositionMonitoringResult:
    readiness: MonitoringReadiness
    status: MonitoringStatus | None
    reason: MonitoringReason
    completed_trading_day: date | None
    latest_close: Decimal | None
    indicator_facts: dict[str, str | bool | None]
    exit_triggered: bool = False
    exit_triggered_on: date | None = None
    exit_trigger_reason: str | None = None
    protective_stop_policy: str = "NONE"
    trailing_stop_policy: str = "NONE"
    profit_target_policy: str = "NONE"


def classify_monitoring(
    *,
    strategy: StrategyName,
    context: StrategyExitContext,
    latest_low: Decimal,
) -> tuple[MonitoringStatus, MonitoringReason]:
    if strategy == StrategyName.EMA20_PULLBACK:
        mapping = {
            StrategyExitState.ABOVE_EMA20: (
                MonitoringStatus.HOLD,
                MonitoringReason.EMA20_HELD,
            ),
            StrategyExitState.BELOW_EMA20_STRONG_TREND: (
                MonitoringStatus.ATTENTION,
                MonitoringReason.EMA20_LOST_STRONG_TREND_HOLD,
            ),
            StrategyExitState.EMA20_WEAK_TREND_BREAKDOWN: (
                MonitoringStatus.SELL,
                MonitoringReason.EMA20_WEAK_TREND_BREAKDOWN,
            ),
            StrategyExitState.EMA50_BREAKDOWN: (
                MonitoringStatus.SELL,
                MonitoringReason.EMA50_BREAKDOWN,
            ),
        }
        if context.current_exit_state not in mapping:
            raise ValueError(MonitoringReason.INSUFFICIENT_HISTORY.value)
        return mapping[context.current_exit_state]

    if context.sma150 is None:
        raise ValueError(MonitoringReason.INSUFFICIENT_HISTORY.value)
    if context.reference_close < context.sma150:
        return MonitoringStatus.SELL, MonitoringReason.SMA150_BREAKDOWN
    if context.reference_close == context.sma150:
        return MonitoringStatus.ATTENTION, MonitoringReason.SMA150_CLOSE_AT_SUPPORT
    if latest_low < context.sma150:
        return (
            MonitoringStatus.ATTENTION,
            MonitoringReason.SMA150_INTRADAY_BREACH_RECOVERED,
        )
    return MonitoringStatus.HOLD, MonitoringReason.SMA150_HELD
