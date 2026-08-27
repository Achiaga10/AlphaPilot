from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.services.research_dataset import GitRevision
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    ClassificationGates,
    DatasetBinding,
    ParameterDeclaration,
    ResearchPeriod,
    StrategyLabProtocol,
    StrategyLabResultSummary,
    StrategySpecification,
    TemporalFold,
)
from alphapilot.strategy_lab.service import StrategyLabService


@pytest.fixture
def dataset() -> DatasetBinding:
    return DatasetBinding(
        snapshot_id=UUID("11111111-1111-1111-1111-111111111111"),
        dataset_sha256="a" * 64,
        universe_sha256="b" * 64,
    )


@pytest.fixture
def candidates() -> tuple[CandidateConfiguration, ...]:
    return (
        CandidateConfiguration(
            label="control",
            parameter_values=(("threshold", Decimal("1")),),
            selection_policy="relative-strength-20",
            sizing_policy="equal-slot",
            cost_scenario=CostScenarioName.COST_LOW,
        ),
        CandidateConfiguration(
            label="candidate",
            parameter_values=(("threshold", Decimal("2")),),
            selection_policy="relative-strength-20",
            sizing_policy="equal-slot",
            cost_scenario=CostScenarioName.COST_LOW,
        ),
    )


@pytest.fixture
def protocol(
    dataset: DatasetBinding,
    candidates: tuple[CandidateConfiguration, ...],
) -> StrategyLabProtocol:
    return StrategyLabProtocol(
        protocol_version=1,
        specification=StrategySpecification(
            strategy_key="fixture-strategy",
            strategy_version=1,
            display_name="Fixture Strategy",
            description="Deterministic infrastructure fixture, not a trading strategy",
            entry_configuration=(("rule", "fixture"),),
            exit_configuration=(("rule", "fixture"),),
            required_lookback_bars=20,
            allowed_selection_policies=("relative-strength-20",),
            allowed_sizing_policies=("equal-slot",),
            parameters=(
                ParameterDeclaration(
                    name="threshold",
                    allowed_values=(Decimal("1"), Decimal("2")),
                ),
            ),
            research_notes=("Acceptance fixture only",),
        ),
        dataset=dataset,
        development_period=ResearchPeriod(date(2021, 1, 1), date(2022, 12, 31)),
        validation_period=ResearchPeriod(date(2023, 1, 1), date(2023, 12, 31)),
        folds=(
            TemporalFold("fold-1", ResearchPeriod(date(2021, 1, 1), date(2021, 12, 31))),
            TemporalFold("fold-2", ResearchPeriod(date(2022, 1, 1), date(2022, 12, 31))),
            TemporalFold("fold-3", ResearchPeriod(date(2023, 1, 1), date(2023, 12, 31))),
        ),
        candidates=candidates,
        gates=ClassificationGates(
            minimum_validation_return_retention_pct=Decimal("50"),
            maximum_validation_drawdown_pct=Decimal("25"),
            minimum_validation_sharpe=Decimal("0.5"),
            minimum_validation_calmar=Decimal("0.5"),
            minimum_folds_beating_reference=2,
        ),
        limitations=("Fixture evidence is not market evidence",),
    )


@pytest.fixture
def result() -> StrategyLabResultSummary:
    return StrategyLabResultSummary(
        final_equity=Decimal("120000"),
        total_return_pct=Decimal("20"),
        cagr_pct=Decimal("9"),
        max_drawdown_pct=Decimal("10"),
        sharpe_ratio=Decimal("1"),
        calmar_ratio=Decimal("0.9"),
        profit_factor=Decimal("1.4"),
        win_rate_pct=Decimal("45"),
        completed_trades=20,
        exposure_pct=Decimal("80"),
        turnover_pct=Decimal("400"),
        realized_pnl=Decimal("15000"),
        unrealized_pnl=Decimal("5000"),
        top_5_positive_pnl_share_pct=Decimal("60"),
    )


@pytest.fixture
def service_factory(
    dataset: DatasetBinding,
    result: StrategyLabResultSummary,
) -> Callable[..., StrategyLabService]:
    def build(
        *,
        resolved: DatasetBinding | None = None,
        runner_result: StrategyLabResultSummary | None = None,
    ) -> StrategyLabService:
        return StrategyLabService(
            runner=lambda **_: runner_result or result,
            dataset_resolver=lambda _: resolved or dataset,
            git_revision_provider=lambda: GitRevision(head="c" * 40, dirty=False),
        )

    return build


@pytest.fixture
def completed_experiment(
    protocol: StrategyLabProtocol, service_factory: Callable[..., StrategyLabService]
):
    service = service_factory()
    experiment = service.run_development(service.define(protocol))
    experiment = service.freeze_configuration(experiment, protocol.candidates[1])
    experiment = service.run_validation(experiment)
    return service, service.run_folds(experiment)
