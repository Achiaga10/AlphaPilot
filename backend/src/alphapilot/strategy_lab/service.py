from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Protocol

from alphapilot.backtesting.cost_scenarios import get_cost_scenario
from alphapilot.services.research_dataset import GitRevision, capture_git_revision
from alphapilot.strategy_lab.identity import experiment_identity
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    ClassificationDecision,
    CostMetadata,
    DatasetBinding,
    ExperimentClassification,
    ExperimentStage,
    ResearchPeriod,
    RunEvidence,
    StrategyLabExperiment,
    StrategyLabProtocol,
    StrategyLabResultSummary,
    StrategyProfileCandidate,
)


class StrategyLabRunner(Protocol):
    def __call__(
        self,
        *,
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
        period: ResearchPeriod,
        fold_label: str | None,
    ) -> StrategyLabResultSummary: ...


class DatasetBindingResolver(Protocol):
    def __call__(self, binding: DatasetBinding) -> DatasetBinding: ...


class StrategyLabService:
    """Enforce the formal research lifecycle independently of execution mechanics."""

    def __init__(
        self,
        *,
        runner: StrategyLabRunner,
        dataset_resolver: DatasetBindingResolver,
        git_revision_provider: Callable[[], GitRevision] = capture_git_revision,
    ) -> None:
        self.runner = runner
        self.dataset_resolver = dataset_resolver
        self.git_revision_provider = git_revision_provider

    def validate_protocol(self, protocol: StrategyLabProtocol) -> None:
        if protocol.protocol_version < 1:
            raise ValueError("protocol version must be positive")
        if not protocol.limitations:
            raise ValueError("formal protocol must declare research limitations")
        if protocol.dataset is None:
            raise ValueError("formal Strategy Lab research requires a frozen dataset snapshot")
        resolved = self.dataset_resolver(protocol.dataset)
        if not resolved.finalized or not resolved.value_reproducible:
            raise ValueError(
                "formal Strategy Lab research requires a finalized reproducible snapshot"
            )
        if resolved != protocol.dataset:
            raise ValueError(
                "dataset snapshot identity or hash does not match the finalized manifest"
            )
        if protocol.development_period.overlaps(protocol.validation_period):
            raise ValueError("development and validation periods must not overlap")
        if protocol.development_period.end >= protocol.validation_period.start:
            raise ValueError("validation must occur after development")
        fold_labels = [fold.label for fold in protocol.folds]
        if len(set(fold_labels)) != len(fold_labels):
            raise ValueError("fold labels must be unique")
        for index, fold in enumerate(protocol.folds):
            for other in protocol.folds[index + 1 :]:
                if fold.period.overlaps(other.period):
                    raise ValueError("temporal folds must not overlap")
        if not protocol.candidates:
            raise ValueError("at least one candidate configuration is required")
        labels = [item.label for item in protocol.candidates]
        if len(set(labels)) != len(labels):
            raise ValueError("candidate labels must be unique")
        for candidate in protocol.candidates:
            self._validate_configuration(protocol, candidate)

    def define(self, protocol: StrategyLabProtocol) -> StrategyLabExperiment:
        self.validate_protocol(protocol)
        return StrategyLabExperiment(
            experiment_id=experiment_identity(protocol),
            protocol=protocol,
        )

    def run_development(self, experiment: StrategyLabExperiment) -> StrategyLabExperiment:
        self._require_stage(experiment, ExperimentStage.DEFINED)
        evidence = tuple(
            self._run(
                experiment.protocol,
                configuration,
                experiment.protocol.development_period,
                ExperimentStage.DEVELOPMENT,
            )
            for configuration in experiment.protocol.candidates
        )
        return replace(
            experiment,
            stage=ExperimentStage.DEVELOPMENT,
            development_evidence=evidence,
        )

    def freeze_configuration(
        self,
        experiment: StrategyLabExperiment,
        configuration: CandidateConfiguration,
    ) -> StrategyLabExperiment:
        self._require_stage(experiment, ExperimentStage.DEVELOPMENT)
        declared = self._declared_configuration(experiment.protocol, configuration)
        if declared not in tuple(item.configuration for item in experiment.development_evidence):
            raise ValueError("frozen configuration must have development evidence")
        return replace(
            experiment,
            experiment_id=experiment_identity(experiment.protocol, declared),
            stage=ExperimentStage.FROZEN,
            frozen_configuration=declared,
        )

    def run_validation(
        self,
        experiment: StrategyLabExperiment,
        configuration: CandidateConfiguration | None = None,
    ) -> StrategyLabExperiment:
        self._require_stage(experiment, ExperimentStage.FROZEN)
        frozen = self._exact_frozen(experiment, configuration)
        evidence = self._run(
            experiment.protocol,
            frozen,
            experiment.protocol.validation_period,
            ExperimentStage.VALIDATION,
        )
        return replace(
            experiment,
            stage=ExperimentStage.VALIDATION,
            validation_evidence=evidence,
        )

    def run_folds(
        self,
        experiment: StrategyLabExperiment,
        configuration: CandidateConfiguration | None = None,
    ) -> StrategyLabExperiment:
        self._require_stage(experiment, ExperimentStage.VALIDATION)
        frozen = self._exact_frozen(experiment, configuration)
        evidence = tuple(
            self._run(
                experiment.protocol,
                frozen,
                fold.period,
                ExperimentStage.FOLDS,
                fold_label=fold.label,
            )
            for fold in experiment.protocol.folds
        )
        return replace(experiment, stage=ExperimentStage.FOLDS, fold_evidence=evidence)

    def classify(self, experiment: StrategyLabExperiment) -> StrategyLabExperiment:
        self._require_stage(experiment, ExperimentStage.FOLDS)
        if (
            experiment.frozen_configuration is None
            or experiment.validation_evidence is None
            or len(experiment.fold_evidence) != len(experiment.protocol.folds)
        ):
            raise ValueError("classification requires complete frozen validation and fold evidence")
        development = next(
            (
                item
                for item in experiment.development_evidence
                if item.configuration == experiment.frozen_configuration
            ),
            None,
        )
        if development is None:
            raise ValueError(
                "classification requires development evidence for frozen configuration"
            )
        gates = experiment.protocol.gates
        validation = experiment.validation_evidence.result
        reasons: list[str] = []
        failed = False

        if development.result.total_return_pct > 0:
            retention = (
                validation.total_return_pct / development.result.total_return_pct * Decimal("100")
            )
            if retention < gates.minimum_validation_return_retention_pct:
                failed = True
                reasons.append("validation return retention gate failed")
        if (
            gates.maximum_validation_drawdown_pct is not None
            and validation.max_drawdown_pct > gates.maximum_validation_drawdown_pct
        ):
            failed = True
            reasons.append("validation drawdown gate failed")
        if not self._minimum_optional(validation.sharpe_ratio, gates.minimum_validation_sharpe):
            failed = True
            reasons.append("validation Sharpe gate failed")
        if not self._minimum_optional(validation.calmar_ratio, gates.minimum_validation_calmar):
            failed = True
            reasons.append("validation Calmar gate failed")
        positive_folds = sum(item.result.total_return_pct > 0 for item in experiment.fold_evidence)
        if positive_folds < gates.minimum_folds_beating_reference:
            failed = True
            reasons.append("fold consistency gate failed")

        if failed:
            classification = ExperimentClassification.REJECTED
        elif validation.total_return_pct > 0 and positive_folds == len(experiment.fold_evidence):
            classification = ExperimentClassification.PROMISING_RESEARCH_BASELINE
            reasons.append("all declared gates passed with positive validation and fold evidence")
        else:
            classification = ExperimentClassification.RESEARCH_ONLY
            reasons.append("declared gates passed but evidence is not consistently positive")
        decision = ClassificationDecision(
            classification=classification,
            reasons=tuple(reasons),
            limitations=experiment.protocol.limitations,
        )
        candidate = (
            StrategyProfileCandidate(
                experiment_id=experiment.experiment_id,
                strategy_key=experiment.protocol.specification.strategy_key,
                strategy_version=experiment.protocol.specification.strategy_version,
                frozen_configuration=experiment.frozen_configuration,
                classification=classification,
                evidence_summary=tuple(reasons),
            )
            if classification == ExperimentClassification.PROMISING_RESEARCH_BASELINE
            else None
        )
        return replace(
            experiment,
            stage=ExperimentStage.CLASSIFIED,
            classification=decision,
            profile_candidate=candidate,
        )

    def _validate_configuration(
        self,
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
    ) -> None:
        spec = protocol.specification
        declarations = {item.name: item.allowed_values for item in spec.parameters}
        supplied = configuration.parameters
        unknown = sorted(set(supplied) - set(declarations))
        missing = sorted(set(declarations) - set(supplied))
        if unknown:
            raise ValueError(f"undeclared parameters: {', '.join(unknown)}")
        if missing:
            raise ValueError(f"missing declared parameters: {', '.join(missing)}")
        for name, value in supplied.items():
            if value not in declarations[name]:
                raise ValueError(f"undeclared value for parameter {name}: {value}")
        if configuration.selection_policy not in spec.allowed_selection_policies:
            raise ValueError("selection policy is not declared by strategy specification")
        if configuration.sizing_policy not in spec.allowed_sizing_policies:
            raise ValueError("sizing policy is not declared by strategy specification")

    @staticmethod
    def _require_stage(experiment: StrategyLabExperiment, expected: ExperimentStage) -> None:
        if experiment.stage != expected:
            raise ValueError(
                f"operation requires {expected.value} stage, got {experiment.stage.value}"
            )

    @staticmethod
    def _declared_configuration(
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
    ) -> CandidateConfiguration:
        for declared in protocol.candidates:
            if declared == configuration:
                return declared
        raise ValueError("configuration was not declared before development")

    @staticmethod
    def _exact_frozen(
        experiment: StrategyLabExperiment,
        configuration: CandidateConfiguration | None,
    ) -> CandidateConfiguration:
        frozen = experiment.frozen_configuration
        if frozen is None:
            raise ValueError("configuration has not been frozen")
        if configuration is not None and configuration != frozen:
            raise ValueError("validation and folds must use the exact frozen configuration")
        return frozen

    def _run(
        self,
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
        period: ResearchPeriod,
        stage: ExperimentStage,
        *,
        fold_label: str | None = None,
    ) -> RunEvidence:
        self._validate_configuration(protocol, configuration)
        revision = self.git_revision_provider()
        scenario = get_cost_scenario(configuration.cost_scenario)
        return RunEvidence(
            stage=stage,
            configuration=configuration,
            period=period,
            fold_label=fold_label,
            result=self.runner(
                protocol=protocol,
                configuration=configuration,
                period=period,
                fold_label=fold_label,
            ),
            git_revision=revision.head,
            git_dirty=revision.dirty,
            cost=CostMetadata(
                scenario=scenario.name,
                commission_per_order=scenario.commission_per_order,
                slippage_bps_per_side=scenario.slippage_bps,
            ),
        )

    @staticmethod
    def _minimum_optional(value: Decimal | None, minimum: Decimal | None) -> bool:
        return minimum is None or (value is not None and value >= minimum)
