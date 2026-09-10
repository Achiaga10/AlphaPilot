from dataclasses import replace
from decimal import Decimal

import pytest

from alphapilot.strategy_lab.achia_ema20_protocol import (
    AchiaGateEvidence,
    build_achia_protocol,
    failed_achia_gates,
    reject_achia_stage,
)
from alphapilot.strategy_lab.identity import experiment_identity
from alphapilot.strategy_lab.models import (
    ExperimentClassification,
    ExperimentStage,
    StrategyLabResultSummary,
)
from alphapilot.strategy_lab.service import StrategyLabService


def result() -> StrategyLabResultSummary:
    return StrategyLabResultSummary(
        final_equity=Decimal("130000"),
        total_return_pct=Decimal("30"),
        cagr_pct=Decimal("10"),
        max_drawdown_pct=Decimal("20"),
        sharpe_ratio=Decimal("0.5"),
        calmar_ratio=Decimal("0.5"),
        profit_factor=Decimal("1.1"),
        win_rate_pct=Decimal("45"),
        completed_trades=100,
        exposure_pct=Decimal("80"),
        turnover_pct=Decimal("500"),
        realized_pnl=Decimal("25000"),
        unrealized_pnl=Decimal("5000"),
        top_5_positive_pnl_share_pct=Decimal("40"),
    )


def test_protocol_one_hypothesis_frozen_identity_and_no_operational_reuse() -> None:
    protocol = build_achia_protocol()
    assert protocol.specification.strategy_key == "achia-strat-ema20-v1"
    assert len(protocol.candidates) == 1
    assert protocol.specification.parameters == ()
    assert experiment_identity(protocol) == experiment_identity(build_achia_protocol())
    assert experiment_identity(protocol, protocol.candidates[0]) != experiment_identity(protocol)
    assert protocol.dataset is not None
    lab = StrategyLabService(
        runner=lambda **_: result(), dataset_resolver=lambda _: protocol.dataset
    )
    experiment = lab.define(protocol)
    with pytest.raises(ValueError, match="FROZEN"):
        lab.run_validation(experiment)
    with pytest.raises(ValueError, match="undeclared parameters"):
        lab.define(
            replace(
                protocol,
                candidates=(
                    replace(protocol.candidates[0], parameter_values=(("atr_period", 30),)),
                ),
            )
        )


def test_gates_are_fixed_and_early_failure_cannot_open_validation() -> None:
    evidence = AchiaGateEvidence(
        result(), Decimal("0.1"), Decimal("100"), Decimal("10"), Decimal("20"), 0
    )
    assert failed_achia_gates(evidence) == ()
    assert failed_achia_gates(evidence, validation=True) == ()
    assert failed_achia_gates(replace(evidence, risk_p90_pct=Decimal("10.001"))) == (
        "stop risk P90 <= 10%",
    )
    assert failed_achia_gates(replace(evidence, pooled_expectancy_pct=Decimal("0"))) == (
        "positive pooled independent expectancy",
    )
    protocol = build_achia_protocol()
    lab = StrategyLabService(
        runner=lambda **_: result(), dataset_resolver=lambda _: protocol.dataset
    )
    initial = lab.define(protocol)
    with pytest.raises(ValueError, match="requires development"):
        reject_achia_stage(initial, ("failed",))
    developed = lab.run_development(initial)
    rejected = reject_achia_stage(developed, ("failed",))
    assert rejected.stage == ExperimentStage.CLASSIFIED
    assert rejected.classification.classification == ExperimentClassification.REJECTED
    assert rejected.profile_candidate is None
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        lab.freeze_configuration(rejected, protocol.candidates[0])


def test_passing_frozen_lifecycle_only_yields_research_candidate() -> None:
    protocol = build_achia_protocol()
    lab = StrategyLabService(
        runner=lambda **_: result(), dataset_resolver=lambda _: protocol.dataset
    )
    experiment = lab.run_development(lab.define(protocol))
    experiment = lab.freeze_configuration(experiment, protocol.candidates[0])
    experiment = lab.classify(lab.run_folds(lab.run_validation(experiment)))
    assert (
        experiment.classification.classification
        == ExperimentClassification.PROMISING_RESEARCH_BASELINE
    )
    assert experiment.profile_candidate.requires_human_review
