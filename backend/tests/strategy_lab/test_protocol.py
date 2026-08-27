from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from alphapilot.backtesting.cost_scenarios import CostScenarioName, get_cost_scenario
from alphapilot.strategy_lab.identity import canonical_json
from alphapilot.strategy_lab.models import CandidateConfiguration, ResearchPeriod, TemporalFold


def test_valid_protocol_and_declared_candidate_are_accepted(
    protocol: Any, service_factory: Any
) -> None:
    experiment = service_factory().define(protocol)
    assert experiment.protocol == protocol
    assert len(experiment.experiment_id) == 64
    scenario = get_cost_scenario(protocol.candidates[0].cost_scenario)
    assert scenario.slippage_bps == Decimal("5")
    assert scenario.commission_per_order == 0


def test_missing_or_unknown_frozen_dataset_is_rejected(
    protocol: Any, dataset: Any, service_factory: Any
) -> None:
    with pytest.raises(ValueError, match="frozen dataset"):
        service_factory().define(replace(protocol, dataset=None))
    unknown = replace(dataset, dataset_sha256="f" * 64)
    with pytest.raises(ValueError, match="does not match"):
        service_factory().define(replace(protocol, dataset=unknown))


def test_nonfinal_or_nonreproducible_dataset_is_rejected(
    protocol: Any, dataset: Any, service_factory: Any
) -> None:
    for invalid in (replace(dataset, finalized=False), replace(dataset, value_reproducible=False)):
        with pytest.raises(ValueError, match="finalized reproducible"):
            service_factory(resolved=invalid).define(replace(protocol, dataset=invalid))


def test_development_validation_overlap_and_order_are_rejected(
    protocol: Any, service_factory: Any
) -> None:
    overlapping = replace(
        protocol,
        validation_period=ResearchPeriod(date(2022, 1, 1), date(2023, 1, 1)),
    )
    with pytest.raises(ValueError, match="must not overlap"):
        service_factory().define(overlapping)


def test_malformed_duplicate_or_overlapping_folds_are_rejected(
    protocol: Any, service_factory: Any
) -> None:
    duplicate = replace(protocol, folds=(protocol.folds[0], protocol.folds[0]))
    with pytest.raises(ValueError, match="labels must be unique"):
        service_factory().define(duplicate)
    overlap = replace(
        protocol,
        folds=(
            TemporalFold("a", ResearchPeriod(date(2021, 1, 1), date(2021, 8, 1))),
            TemporalFold("b", ResearchPeriod(date(2021, 8, 1), date(2022, 1, 1))),
        ),
    )
    with pytest.raises(ValueError, match="must not overlap"):
        service_factory().define(overlap)


def test_period_constructor_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="start"):
        ResearchPeriod(date(2024, 2, 1), date(2024, 1, 1))


def test_undeclared_parameter_and_value_are_rejected(protocol: Any, service_factory: Any) -> None:
    unknown = replace(protocol.candidates[0], parameter_values=(("new", 1),))
    with pytest.raises(ValueError, match="undeclared parameters"):
        service_factory().define(replace(protocol, candidates=(unknown,)))
    value = replace(protocol.candidates[0], parameter_values=(("threshold", Decimal("3")),))
    with pytest.raises(ValueError, match="undeclared value"):
        service_factory().define(replace(protocol, candidates=(value,)))


def test_missing_parameter_or_disallowed_policy_is_rejected(
    protocol: Any, service_factory: Any
) -> None:
    missing = replace(protocol.candidates[0], parameter_values=())
    with pytest.raises(ValueError, match="missing declared"):
        service_factory().define(replace(protocol, candidates=(missing,)))
    sizing = replace(protocol.candidates[0], sizing_policy="atr-risk")
    with pytest.raises(ValueError, match="sizing policy"):
        service_factory().define(replace(protocol, candidates=(sizing,)))


def test_cost_scenario_is_required_and_protocol_serialization_is_deterministic(
    protocol: Any,
) -> None:
    assert protocol.candidates[0].cost_scenario == CostScenarioName.COST_LOW
    assert canonical_json(protocol) == canonical_json(protocol)


def test_configuration_rejects_duplicate_parameter_names() -> None:
    with pytest.raises(ValueError, match="unique"):
        CandidateConfiguration(
            label="bad",
            parameter_values=(("x", 1), ("x", 2)),
            selection_policy="relative-strength-20",
            sizing_policy="equal-slot",
            cost_scenario=CostScenarioName.COST_LOW,
        )
