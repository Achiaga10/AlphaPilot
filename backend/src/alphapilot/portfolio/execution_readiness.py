from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ExecutionReadiness(StrEnum):
    ACTIONABLE = "ACTIONABLE"
    PAPER_FORWARD_ONLY = "PAPER_FORWARD_ONLY"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class ExecutionReadinessReason(StrEnum):
    LOSS_CONTROL_READY = "LOSS_CONTROL_READY"
    NO_APPROVED_LOSS_CONTROL_POLICY = "NO_APPROVED_LOSS_CONTROL_POLICY"
    MISSING_NUMERIC_BOUNDARY = "MISSING_NUMERIC_BOUNDARY"
    MISSING_TRIGGER_SEMANTICS = "MISSING_TRIGGER_SEMANTICS"
    NOT_A_NEW_BUY = "NOT_A_NEW_BUY"
    NEWS_RISK_BLOCK = "NEWS_RISK_BLOCK"
    NEWS_ASSESSMENT_UNAVAILABLE = "NEWS_ASSESSMENT_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class LossControlEvidence:
    policy_name: str
    boundary_price: Decimal
    distance_dollars: Decimal
    distance_pct: Decimal
    trigger: str
    strategy_profile_id: str
    strategy_profile_version: int
    classification: str
    broker_stop_order: bool = False

    def __post_init__(self) -> None:
        if (
            min(
                self.boundary_price,
                self.distance_dollars,
                self.distance_pct,
            )
            <= 0
        ):
            raise ValueError("loss-control evidence requires positive numeric values")
        if not self.trigger.strip() or not self.policy_name.strip():
            raise ValueError("loss-control evidence requires policy and trigger semantics")


ProtectiveStopEvidence = LossControlEvidence


def classify_new_buy(
    stop: LossControlEvidence | None,
) -> tuple[ExecutionReadiness, ExecutionReadinessReason]:
    if stop is None:
        return (
            ExecutionReadiness.RESEARCH_ONLY,
            ExecutionReadinessReason.NO_APPROVED_LOSS_CONTROL_POLICY,
        )
    return ExecutionReadiness.ACTIONABLE, ExecutionReadinessReason.LOSS_CONTROL_READY
