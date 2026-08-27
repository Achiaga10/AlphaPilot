from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from alphapilot.strategy_lab.models import ExperimentStage


def test_development_runs_every_declared_candidate(protocol: Any, service_factory: Any) -> None:
    experiment = service_factory().run_development(service_factory().define(protocol))
    assert experiment.stage == ExperimentStage.DEVELOPMENT
    assert (
        tuple(item.configuration for item in experiment.development_evidence) == protocol.candidates
    )


def test_freeze_selects_one_declared_developed_configuration(
    protocol: Any, service_factory: Any
) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[1])
    assert frozen.stage == ExperimentStage.FROZEN
    assert frozen.frozen_configuration is protocol.candidates[1]
    assert developed.frozen_configuration is None


def test_freeze_rejects_undeclared_configuration(protocol: Any, service_factory: Any) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    with pytest.raises(ValueError, match="not declared"):
        service.freeze_configuration(
            developed,
            replace(protocol.candidates[0], label="post-hoc"),
        )


def test_validation_before_freeze_is_rejected(protocol: Any, service_factory: Any) -> None:
    service = service_factory()
    with pytest.raises(ValueError, match="FROZEN"):
        service.run_validation(service.define(protocol))


def test_validation_rejects_different_configuration(protocol: Any, service_factory: Any) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[0])
    with pytest.raises(ValueError, match="exact frozen"):
        service.run_validation(frozen, protocol.candidates[1])


def test_validation_accepts_exact_frozen_configuration(protocol: Any, service_factory: Any) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[0])
    validated = service.run_validation(frozen, protocol.candidates[0])
    assert validated.validation_evidence is not None
    assert validated.validation_evidence.configuration == frozen.frozen_configuration


def test_folds_before_validation_are_rejected(protocol: Any, service_factory: Any) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[0])
    with pytest.raises(ValueError, match="VALIDATION"):
        service.run_folds(frozen)


def test_folds_use_exact_frozen_configuration(protocol: Any, service_factory: Any) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[0])
    validated = service.run_validation(frozen)
    with pytest.raises(ValueError, match="exact frozen"):
        service.run_folds(validated, protocol.candidates[1])
    folded = service.run_folds(validated)
    assert [item.fold_label for item in folded.fold_evidence] == [
        "fold-1",
        "fold-2",
        "fold-3",
    ]
    assert all(item.configuration == frozen.frozen_configuration for item in folded.fold_evidence)


def test_classification_before_required_evidence_is_rejected(
    protocol: Any, service_factory: Any
) -> None:
    service = service_factory()
    with pytest.raises(ValueError, match="FOLDS"):
        service.classify(service.define(protocol))


def test_repeated_validation_cannot_mutate_frozen_configuration(
    protocol: Any, service_factory: Any
) -> None:
    service = service_factory()
    developed = service.run_development(service.define(protocol))
    frozen = service.freeze_configuration(developed, protocol.candidates[0])
    validated = service.run_validation(frozen)
    with pytest.raises(ValueError, match="FROZEN"):
        service.run_validation(validated)
    assert validated.frozen_configuration == protocol.candidates[0]


def test_frozen_configuration_is_immutable(protocol: Any) -> None:
    with pytest.raises(FrozenInstanceError):
        protocol.candidates[0].label = "changed"  # type: ignore[misc]
