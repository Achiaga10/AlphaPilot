from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from alphapilot.backtesting.models import BacktestBarResult


@dataclass(slots=True, frozen=True)
class ExecutableCandidate:
    ticker: str
    signal_bar: BacktestBarResult
    execution_bar: BacktestBarResult
    ranking_score: Decimal | None = None


class SelectionPolicyName(StrEnum):
    TICKER_ASCENDING = "ticker-ascending"
    RELATIVE_STRENGTH_20 = "relative-strength-20"


class CandidateRejectionReason(StrEnum):
    SLOTS_FULL = "slots-full"
    INSUFFICIENT_ALLOCATION = "insufficient-allocation"


class CandidateSelectionPolicy(Protocol):
    name: str
    uses_scores: bool

    def order(
        self,
        candidates: list[ExecutableCandidate],
    ) -> list[ExecutableCandidate]: ...


class TickerAscendingSelectionPolicy:
    """Stable non-alpha baseline used only to validate portfolio plumbing."""

    name = "ticker-ascending-baseline"
    uses_scores = False

    def order(
        self,
        candidates: list[ExecutableCandidate],
    ) -> list[ExecutableCandidate]:
        return sorted(candidates, key=lambda candidate: candidate.ticker)


class RelativeStrength20SelectionPolicy:
    """Ranks scored candidates by RS20 and uses ticker order as fallback."""

    name = SelectionPolicyName.RELATIVE_STRENGTH_20.value
    uses_scores = True

    def order(
        self,
        candidates: list[ExecutableCandidate],
    ) -> list[ExecutableCandidate]:
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.ranking_score is None,
                (-candidate.ranking_score if candidate.ranking_score is not None else Decimal("0")),
                candidate.ticker,
            ),
        )


def create_selection_policy(
    policy_name: SelectionPolicyName,
) -> CandidateSelectionPolicy:
    if policy_name == SelectionPolicyName.RELATIVE_STRENGTH_20:
        return RelativeStrength20SelectionPolicy()

    return TickerAscendingSelectionPolicy()
