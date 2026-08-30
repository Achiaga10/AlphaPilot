from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from alphapilot.services.position_intelligence import PositionIntelligence


class GuidanceCategory(StrEnum):
    ACTIVE_POLICY = "ACTIVE_POLICY"
    STRATEGY_EXIT_REFERENCE = "STRATEGY_EXIT_REFERENCE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    NONE = "NONE"
    UNAVAILABLE = "UNAVAILABLE"


class ExitReferenceType(StrEnum):
    EMA50_HARD_BREAKDOWN = "EMA50_HARD_BREAKDOWN"
    EMA20_CONDITIONAL_BREAKDOWN = "EMA20_CONDITIONAL_BREAKDOWN"
    SMA150_BREAKDOWN = "SMA150_BREAKDOWN"


@dataclass(frozen=True, slots=True)
class ExitReference:
    reference_type: ExitReferenceType
    value: Decimal
    condition: str
    qualifier: str
    distance_dollars: Decimal | None = None
    distance_pct: Decimal | None = None


@dataclass(frozen=True, slots=True)
class StopExitGuidance:
    category: GuidanceCategory
    as_of_date: date | None
    protective_stop: str
    trailing_stop: str
    profit_target: str
    references: tuple[ExitReference, ...]
    research_only_candidate: str | None
    research_only_status: str | None
    monitoring_status: str | None
    sticky_sell_triggered: bool
    explanation: str
    loss_control_policy: str = "NONE"
    current_loss_control_boundary: Decimal | None = None
    loss_control_trigger: str | None = None
    loss_control_active: bool = False
    broker_stop_order: bool = False


class StopExitGuidanceService:
    """Translate authoritative Position Intelligence into explicit exit semantics."""

    def build(self, intelligence: PositionIntelligence) -> StopExitGuidance:
        if not intelligence.strategy_guidance_available:
            return StopExitGuidance(
                GuidanceCategory.UNAVAILABLE,
                intelligence.monitoring_completed_trading_day,
                "UNAVAILABLE",
                "UNAVAILABLE",
                "UNAVAILABLE",
                (),
                None,
                None,
                None,
                False,
                "Strategy exit guidance is unavailable; no stop or exit level is inferred.",
            )
        references: list[ExitReference] = []
        if intelligence.strategy_profile_id == "ema20-pullback-v1":
            self._append(
                references,
                intelligence.indicator_facts.get("ema50"),
                ExitReferenceType.EMA50_HARD_BREAKDOWN,
                "COMPLETED_DAILY_CLOSE_BELOW",
                "A completed daily close below EMA50 triggers SELL.",
                intelligence.latest_completed_close,
            )
            self._append(
                references,
                intelligence.indicator_facts.get("ema20"),
                ExitReferenceType.EMA20_CONDITIONAL_BREAKDOWN,
                "COMPLETED_DAILY_CLOSE_BELOW_CONDITIONAL",
                (
                    "Conditional under frozen HYBRID 2%: EMA20 loss triggers SELL only "
                    "when the strong-trend exception is not satisfied."
                ),
                intelligence.latest_completed_close,
            )
        elif intelligence.strategy_profile_id == "micho-150-v1":
            self._append(
                references,
                intelligence.indicator_facts.get("sma150"),
                ExitReferenceType.SMA150_BREAKDOWN,
                "COMPLETED_DAILY_CLOSE_BELOW",
                "A completed daily close below SMA150 triggers SELL; an intraday touch does not.",
                intelligence.latest_completed_close,
            )
        micho_reference = next(
            (
                item
                for item in references
                if item.reference_type == ExitReferenceType.SMA150_BREAKDOWN
            ),
            None,
        )
        category = (
            GuidanceCategory.ACTIVE_POLICY
            if micho_reference is not None
            else GuidanceCategory.STRATEGY_EXIT_REFERENCE
            if references
            else GuidanceCategory.UNAVAILABLE
        )
        return StopExitGuidance(
            category,
            intelligence.monitoring_completed_trading_day,
            intelligence.protective_stop_policy,
            intelligence.trailing_stop_policy,
            intelligence.profit_target_policy,
            tuple(references),
            intelligence.research_only_stop_candidate,
            intelligence.research_only_stop_status,
            intelligence.monitoring_status,
            intelligence.exit_triggered,
            (
                "The SMA150 completed-close rule is active strategy loss control, "
                "not an intraday broker stop order."
                if micho_reference is not None
                else "No active protective stop exists. Strategy references use completed "
                "daily closes and are not broker stop orders."
            ),
            "SMA150_COMPLETED_CLOSE_EXIT" if micho_reference is not None else "NONE",
            micho_reference.value if micho_reference is not None else None,
            "COMPLETED_DAILY_CLOSE_BELOW" if micho_reference is not None else None,
            micho_reference is not None,
            False,
        )

    @staticmethod
    def _append(
        output: list[ExitReference],
        raw: object,
        reference_type: ExitReferenceType,
        condition: str,
        qualifier: str,
        latest_close: Decimal | None,
    ) -> None:
        if raw is None:
            return
        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            return
        close = latest_close
        distance = close - value if close is not None else None
        distance_pct = (
            distance / close * Decimal("100")
            if distance is not None and close is not None and close > 0
            else None
        )
        output.append(
            ExitReference(reference_type, value, condition, qualifier, distance, distance_pct)
        )
