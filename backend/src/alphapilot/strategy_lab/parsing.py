from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    ClassificationGates,
    DatasetBinding,
    ParameterDeclaration,
    ResearchPeriod,
    StrategyLabProtocol,
    StrategySpecification,
    TemporalFold,
)


def parse_protocol(data: dict[str, Any]) -> StrategyLabProtocol:
    specification = data["specification"]
    dataset = data.get("dataset")
    return StrategyLabProtocol(
        protocol_version=int(data["protocol_version"]),
        specification=StrategySpecification(
            strategy_key=str(specification["strategy_key"]),
            strategy_version=int(specification["strategy_version"]),
            display_name=str(specification["display_name"]),
            description=str(specification["description"]),
            entry_configuration=_pairs(specification.get("entry_configuration", {})),
            exit_configuration=_pairs(specification.get("exit_configuration", {})),
            required_lookback_bars=int(specification["required_lookback_bars"]),
            allowed_selection_policies=tuple(specification["allowed_selection_policies"]),
            allowed_sizing_policies=tuple(specification["allowed_sizing_policies"]),
            parameters=tuple(
                ParameterDeclaration(
                    name=str(item["name"]),
                    allowed_values=tuple(_scalar(value) for value in item["allowed_values"]),
                )
                for item in specification["parameters"]
            ),
            research_notes=tuple(specification.get("research_notes", ())),
        ),
        dataset=(
            DatasetBinding(
                snapshot_id=UUID(dataset["snapshot_id"]),
                dataset_sha256=str(dataset["dataset_sha256"]),
                universe_sha256=str(dataset["universe_sha256"]),
                finalized=bool(dataset.get("finalized", True)),
                value_reproducible=bool(dataset.get("value_reproducible", True)),
            )
            if dataset is not None
            else None
        ),
        development_period=_period(data["development_period"]),
        validation_period=_period(data["validation_period"]),
        folds=tuple(
            TemporalFold(label=str(item["label"]), period=_period(item["period"]))
            for item in data["folds"]
        ),
        candidates=tuple(_candidate(item) for item in data["candidates"]),
        gates=_gates(data.get("gates", {})),
        limitations=tuple(data.get("limitations", ())),
    )


def _candidate(data: dict[str, Any]) -> CandidateConfiguration:
    return CandidateConfiguration(
        label=str(data["label"]),
        parameter_values=_pairs(data["parameter_values"]),
        selection_policy=str(data["selection_policy"]),
        sizing_policy=str(data["sizing_policy"]),
        cost_scenario=CostScenarioName(data["cost_scenario"]),
    )


def _period(data: dict[str, Any]) -> ResearchPeriod:
    return ResearchPeriod(
        start=date.fromisoformat(data["start"]), end=date.fromisoformat(data["end"])
    )


def _pairs(data: dict[str, Any] | list[list[Any]]) -> tuple[tuple[str, Any], ...]:
    items: list[tuple[str, Any]]
    if isinstance(data, dict):
        items = list(data.items())
    else:
        items = [(str(item[0]), item[1]) for item in data]
    return tuple((str(key), _scalar(value)) for key, value in sorted(items))


def _scalar(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return value
    if value is None or isinstance(value, (str, int, bool, Decimal)):
        return value
    raise ValueError("Strategy Lab parameter values must be JSON scalars")


def _gates(data: dict[str, Any]) -> ClassificationGates:
    def decimal_value(name: str, default: str | None = None) -> Decimal | None:
        value = data.get(name, default)
        return Decimal(str(value)) if value is not None else None

    return ClassificationGates(
        minimum_validation_return_retention_pct=(
            decimal_value("minimum_validation_return_retention_pct", "0") or Decimal("0")
        ),
        maximum_validation_drawdown_pct=decimal_value("maximum_validation_drawdown_pct"),
        minimum_validation_sharpe=decimal_value("minimum_validation_sharpe"),
        minimum_validation_calmar=decimal_value("minimum_validation_calmar"),
        minimum_folds_beating_reference=int(data.get("minimum_folds_beating_reference", 0)),
    )
