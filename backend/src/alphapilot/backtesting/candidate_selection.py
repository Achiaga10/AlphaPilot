from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from alphapilot.backtesting.models import BacktestBarResult


@dataclass(slots=True, frozen=True)
class ExecutableCandidate:
    ticker: str
    signal_bar: BacktestBarResult
    execution_bar: BacktestBarResult


class CandidateSelectionPolicy(Protocol):
    name: str

    def order(
        self,
        candidates: list[ExecutableCandidate],
    ) -> list[ExecutableCandidate]: ...


class TickerAscendingSelectionPolicy:
    """Stable non-alpha baseline used only to validate portfolio plumbing."""

    name = "ticker-ascending-baseline"

    def order(
        self,
        candidates: list[ExecutableCandidate],
    ) -> list[ExecutableCandidate]:
        return sorted(candidates, key=lambda candidate: candidate.ticker)
