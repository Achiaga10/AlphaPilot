from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from alphapilot.backtesting.cost_scenarios import CostScenarioName

type Scalar = str | int | bool | Decimal | None


class ExperimentStage(StrEnum):
    DEFINED = "DEFINED"
    DEVELOPMENT = "DEVELOPMENT"
    FROZEN = "FROZEN"
    VALIDATION = "VALIDATION"
    FOLDS = "FOLDS"
    CLASSIFIED = "CLASSIFIED"


class ExperimentClassification(StrEnum):
    REJECTED = "REJECTED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    PROMISING_RESEARCH_BASELINE = "PROMISING_RESEARCH_BASELINE"


@dataclass(slots=True, frozen=True)
class ResearchPeriod:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("period start must not exceed end")

    def overlaps(self, other: ResearchPeriod) -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(slots=True, frozen=True)
class TemporalFold:
    label: str
    period: ResearchPeriod

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("fold label must not be empty")


@dataclass(slots=True, frozen=True)
class ParameterDeclaration:
    name: str
    allowed_values: tuple[Scalar, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("parameter name must not be empty")
        if not self.allowed_values:
            raise ValueError(f"parameter {self.name} must declare candidate values")
        if len({_scalar_key(value) for value in self.allowed_values}) != len(self.allowed_values):
            raise ValueError(f"parameter {self.name} contains duplicate candidate values")


@dataclass(slots=True, frozen=True)
class StrategySpecification:
    strategy_key: str
    strategy_version: int
    display_name: str
    description: str
    entry_configuration: tuple[tuple[str, Scalar], ...]
    exit_configuration: tuple[tuple[str, Scalar], ...]
    required_lookback_bars: int
    allowed_selection_policies: tuple[str, ...]
    allowed_sizing_policies: tuple[str, ...]
    parameters: tuple[ParameterDeclaration, ...]
    research_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.strategy_key.strip() or not self.display_name.strip():
            raise ValueError("strategy key and display name are required")
        if self.strategy_version < 1 or self.required_lookback_bars < 1:
            raise ValueError("strategy version and required lookback must be positive")
        names = [item.name for item in self.parameters]
        if len(set(names)) != len(names):
            raise ValueError("strategy parameter declarations must have unique names")
        if not self.allowed_selection_policies or not self.allowed_sizing_policies:
            raise ValueError("at least one selection and sizing policy must be allowed")


@dataclass(slots=True, frozen=True)
class CandidateConfiguration:
    label: str
    parameter_values: tuple[tuple[str, Scalar], ...]
    selection_policy: str
    sizing_policy: str
    cost_scenario: CostScenarioName

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("configuration label must not be empty")
        names = [name for name, _ in self.parameter_values]
        if len(set(names)) != len(names):
            raise ValueError("configuration parameter names must be unique")

    @property
    def parameters(self) -> dict[str, Scalar]:
        return dict(self.parameter_values)


@dataclass(slots=True, frozen=True)
class DatasetBinding:
    snapshot_id: UUID
    dataset_sha256: str
    universe_sha256: str
    finalized: bool = True
    value_reproducible: bool = True


@dataclass(slots=True, frozen=True)
class ClassificationGates:
    minimum_validation_return_retention_pct: Decimal = Decimal("0")
    maximum_validation_drawdown_pct: Decimal | None = None
    minimum_validation_sharpe: Decimal | None = None
    minimum_validation_calmar: Decimal | None = None
    minimum_folds_beating_reference: int = 0

    def __post_init__(self) -> None:
        if self.minimum_validation_return_retention_pct < 0:
            raise ValueError("return retention gate cannot be negative")
        if self.minimum_folds_beating_reference < 0:
            raise ValueError("fold gate cannot be negative")


@dataclass(slots=True, frozen=True)
class StrategyLabProtocol:
    protocol_version: int
    specification: StrategySpecification
    dataset: DatasetBinding | None
    development_period: ResearchPeriod
    validation_period: ResearchPeriod
    folds: tuple[TemporalFold, ...]
    candidates: tuple[CandidateConfiguration, ...]
    gates: ClassificationGates = field(default_factory=ClassificationGates)
    limitations: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class StrategyLabResultSummary:
    final_equity: Decimal
    total_return_pct: Decimal
    cagr_pct: Decimal | None
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal | None
    calmar_ratio: Decimal | None
    profit_factor: Decimal | None
    win_rate_pct: Decimal
    completed_trades: int
    exposure_pct: Decimal
    turnover_pct: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    top_5_positive_pnl_share_pct: Decimal | None


@dataclass(slots=True, frozen=True)
class CostMetadata:
    scenario: CostScenarioName
    commission_per_order: Decimal
    slippage_bps_per_side: Decimal


@dataclass(slots=True, frozen=True)
class RunEvidence:
    stage: ExperimentStage
    configuration: CandidateConfiguration
    period: ResearchPeriod
    result: StrategyLabResultSummary
    git_revision: str
    git_dirty: bool
    cost: CostMetadata
    fold_label: str | None = None


@dataclass(slots=True, frozen=True)
class ClassificationDecision:
    classification: ExperimentClassification
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class StrategyProfileCandidate:
    experiment_id: str
    strategy_key: str
    strategy_version: int
    frozen_configuration: CandidateConfiguration
    classification: ExperimentClassification
    evidence_summary: tuple[str, ...]
    requires_human_review: bool = True


@dataclass(slots=True, frozen=True)
class StrategyLabExperiment:
    experiment_id: str
    protocol: StrategyLabProtocol
    stage: ExperimentStage = ExperimentStage.DEFINED
    development_evidence: tuple[RunEvidence, ...] = ()
    frozen_configuration: CandidateConfiguration | None = None
    validation_evidence: RunEvidence | None = None
    fold_evidence: tuple[RunEvidence, ...] = ()
    classification: ClassificationDecision | None = None
    profile_candidate: StrategyProfileCandidate | None = None


def _scalar_key(value: Scalar) -> tuple[str, str]:
    return type(value).__name__, str(value)
