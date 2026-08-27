from dataclasses import replace
from decimal import Decimal
from enum import Enum
from types import SimpleNamespace
from typing import Any

import pytest

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.strategy.profile import list_strategy_profiles
from alphapilot.strategy_lab.identity import experiment_identity
from alphapilot.strategy_lab.models import (
    ExperimentClassification,
    ExperimentStage,
    StrategyLabResultSummary,
)
from alphapilot.strategy_lab.reporting import to_json_data
from alphapilot.strategy_lab.results import summarize_portfolio_result


def test_same_protocol_same_identity_and_candidate_order_is_semantically_unordered(
    protocol: Any,
) -> None:
    assert experiment_identity(protocol) == experiment_identity(protocol)
    reordered = replace(protocol, candidates=tuple(reversed(protocol.candidates)))
    assert experiment_identity(protocol) == experiment_identity(reordered)


@pytest.mark.parametrize(
    "changed",
    (
        "strategy",
        "dataset",
        "cost",
        "validation",
    ),
)
def test_material_research_input_changes_identity(protocol: Any, changed: str) -> None:
    if changed == "strategy":
        replacement = replace(
            protocol,
            specification=replace(protocol.specification, strategy_version=2),
        )
    elif changed == "dataset":
        replacement = replace(
            protocol,
            dataset=replace(protocol.dataset, dataset_sha256="d" * 64),
        )
    elif changed == "cost":
        candidate = replace(
            protocol.candidates[0], cost_scenario=CostScenarioName.COST_CONSERVATIVE
        )
        replacement = replace(protocol, candidates=(candidate, protocol.candidates[1]))
    else:
        period = replace(
            protocol.validation_period, end=protocol.validation_period.end.replace(day=30)
        )
        replacement = replace(protocol, validation_period=period)
    assert experiment_identity(protocol) != experiment_identity(replacement)


def test_same_frozen_inputs_produce_deterministic_results(
    protocol: Any, service_factory: Any
) -> None:
    def run_once() -> Any:
        service = service_factory()
        developed = service.run_development(service.define(protocol))
        frozen = service.freeze_configuration(developed, protocol.candidates[1])
        return service.run_validation(frozen)

    first = run_once()
    second = run_once()
    assert first.experiment_id == second.experiment_id
    assert first.validation_evidence == second.validation_evidence


def test_different_frozen_configuration_changes_experiment_identity(
    protocol: Any, service_factory: Any
) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    first = service.freeze_configuration(developed, protocol.candidates[0])
    second = service.freeze_configuration(developed, protocol.candidates[1])
    assert first.experiment_id != second.experiment_id


def test_operational_mutation_cannot_affect_snapshot_bound_result(
    protocol: Any, service_factory: Any
) -> None:
    operational = {"close": Decimal("100")}
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[0])
    first = service.run_validation(frozen).validation_evidence
    operational["close"] = Decimal("999")
    service_again = service_factory()
    developed_again = service_again.run_development(service_again.define(protocol))
    frozen_again = service_again.freeze_configuration(developed_again, protocol.candidates[0])
    second = service_again.run_validation(frozen_again).validation_evidence
    assert first == second


def test_output_metadata_contains_snapshot_hash_and_git_facts(
    protocol: Any, completed_experiment: Any
) -> None:
    _, experiment = completed_experiment
    data = to_json_data(experiment)
    assert data["protocol"]["dataset"]["snapshot_id"] == str(protocol.dataset.snapshot_id)
    assert data["protocol"]["dataset"]["dataset_sha256"] == "a" * 64
    assert data["protocol"]["dataset"]["universe_sha256"] == "b" * 64
    assert data["fold_evidence"][0]["git_revision"] == "c" * 40
    assert data["fold_evidence"][0]["git_dirty"] is False
    assert data["fold_evidence"][0]["cost"] == {
        "scenario": "cost-low",
        "commission_per_order": "0",
        "slippage_bps_per_side": "5",
    }


def test_promising_classification_creates_human_review_candidate_only(
    completed_experiment: Any,
) -> None:
    service, experiment = completed_experiment
    profiles_before = list_strategy_profiles()
    classified = service.classify(experiment)
    assert classified.stage == ExperimentStage.CLASSIFIED
    assert classified.classification.classification == (
        ExperimentClassification.PROMISING_RESEARCH_BASELINE
    )
    assert classified.classification.reasons
    assert classified.classification.limitations
    assert classified.profile_candidate is not None
    assert classified.profile_candidate.requires_human_review is True
    assert list_strategy_profiles() is profiles_before


def test_rejected_classification_is_supported(
    protocol: Any, result: Any, service_factory: Any
) -> None:
    weak = replace(result, max_drawdown_pct=Decimal("50"))
    service = service_factory(runner_result=weak)
    experiment = service.run_development(service.define(protocol))
    experiment = service.freeze_configuration(experiment, protocol.candidates[0])
    experiment = service.run_validation(experiment)
    classified = service.classify(service.run_folds(experiment))
    assert classified.classification.classification == ExperimentClassification.REJECTED
    assert classified.profile_candidate is None


def test_research_only_classification_is_supported(
    protocol: Any, result: Any, service_factory: Any
) -> None:
    flat = replace(result, total_return_pct=Decimal("0"))
    service = service_factory(runner_result=flat)
    permissive = replace(
        protocol,
        gates=replace(protocol.gates, minimum_folds_beating_reference=0),
    )
    experiment = service.run_development(service.define(permissive))
    experiment = service.freeze_configuration(experiment, permissive.candidates[0])
    experiment = service.run_validation(experiment)
    classified = service.classify(service.run_folds(experiment))
    assert classified.classification.classification == ExperimentClassification.RESEARCH_ONLY
    assert classified.profile_candidate is None


def test_production_ready_classification_is_impossible() -> None:
    with pytest.raises(ValueError):
        ExperimentClassification("PRODUCTION_READY")
    assert all(item.value != "PRODUCTION_READY" for item in ExperimentClassification)


def test_result_schema_carries_all_required_metrics(result: StrategyLabResultSummary) -> None:
    data = to_json_data(result)
    assert set(data) == {
        "final_equity",
        "total_return_pct",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
        "calmar_ratio",
        "profit_factor",
        "win_rate_pct",
        "completed_trades",
        "exposure_pct",
        "turnover_pct",
        "realized_pnl",
        "unrealized_pnl",
        "top_5_positive_pnl_share_pct",
    }


def test_existing_portfolio_metrics_are_reused_without_recalculation(result: Any) -> None:
    metrics = SimpleNamespace(
        **{
            name: getattr(result, name)
            for name in (
                "final_equity",
                "total_return_pct",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe_ratio",
                "calmar_ratio",
                "profit_factor",
                "win_rate_pct",
                "completed_trades",
                "exposure_pct",
                "turnover_pct",
            )
        }
    )
    attribution = SimpleNamespace(
        realized_pnl=result.realized_pnl,
        unrealized_pnl=result.unrealized_pnl,
        top_5_positive_pnl_share_pct=result.top_5_positive_pnl_share_pct,
    )
    assert (
        summarize_portfolio_result(
            SimpleNamespace(metrics=metrics, attribution=attribution)  # type: ignore[arg-type]
        )
        == result
    )


def test_classification_enum_is_machine_readable() -> None:
    assert issubclass(ExperimentClassification, Enum)
