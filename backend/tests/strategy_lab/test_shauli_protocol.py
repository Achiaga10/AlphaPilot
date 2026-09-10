from dataclasses import replace
from decimal import Decimal as D

import pytest

from alphapilot.strategy_lab.identity import experiment_identity
from alphapilot.strategy_lab.models import ExperimentStage, StrategyLabExperiment
from alphapilot.strategy_lab.shauli_protocol import build_shauli_protocol, gate_checks, reject_stage


def passing_summary():
    return {
        "metrics": {
            "completed_trades": 100,
            "total_return_pct": D(10),
            "cagr_pct": D(3),
            "sharpe_ratio": D(".5"),
            "calmar_ratio": D(".5"),
            "profit_factor": D("1.1"),
        },
        "risk_pct": {"p90": D(10), "max": D(20)},
        "independent": {"expectancy_pct": D(".01")},
        "valid_provenance_pct": D(100),
        "minimum_cash": D(0),
        "maximum_simultaneous_positions": 10,
        "attribution": {"reconciliation_residual": D(0)},
    }


def test_protocol_is_single_frozen_daily_long_only_no_sweep():
    protocol = build_shauli_protocol()
    assert protocol.specification.strategy_key == "shauli-strat-v1"
    assert protocol.specification.strategy_version == 1
    assert len(protocol.candidates) == 1 and protocol.specification.parameters == ()
    assert dict(protocol.specification.entry_configuration)["direction"] == "LONG_ONLY"
    assert dict(protocol.specification.entry_configuration)["initial_rr"] == 2
    assert (
        dict(protocol.specification.exit_configuration)["entry_target_no_stop_open_between"]
        == "AMBIGUOUS_ENTRY_TARGET_ORDER_CANCEL_NO_TRADE"
    )
    assert experiment_identity(protocol) == experiment_identity(build_shauli_protocol())
    changed = replace(protocol, protocol_version=2)
    assert experiment_identity(protocol) != experiment_identity(changed)


def test_exact_gate_boundaries_pass():
    assert all(gate_checks(passing_summary(), verified=True, unexplained=0).values())


@pytest.mark.parametrize(
    "name,value",
    [
        ("completed_trades", 99),
        ("total_return_pct", D(0)),
        ("cagr_pct", D(0)),
        ("sharpe_ratio", D(".499")),
        ("calmar_ratio", None),
        ("profit_factor", D(1)),
    ],
)
def test_every_economic_failure_closes_stage(name, value):
    summary = passing_summary()
    summary["metrics"][name] = value
    assert not all(gate_checks(summary, verified=True, unexplained=0).values())


@pytest.mark.parametrize("name,value", [("p90", D("10.001")), ("max", D("20.001")), ("p90", None)])
def test_exact_stop_distance_gates(name, value):
    summary = passing_summary()
    summary["risk_pct"][name] = value
    assert not all(gate_checks(summary, verified=True, unexplained=0).values())


def test_data_cash_provenance_reconciliation_gates():
    summary = passing_summary()
    assert not all(gate_checks(summary, verified=False, unexplained=0).values())
    assert not all(gate_checks(summary, verified=True, unexplained=1).values())
    summary.update(minimum_cash=D(-1), maximum_simultaneous_positions=11, valid_provenance_pct=None)
    summary["attribution"]["reconciliation_residual"] = D(".01")
    summary["independent"]["expectancy_pct"] = None
    checks = gate_checks(summary, verified=True, unexplained=0)
    assert not checks["nonnegative_cash"] and not checks["max_positions_respected"]
    assert not checks["valid_stop_target_provenance_100_pct"]
    assert not checks["accounting_reconciles"] and not checks["positive_independent_expectancy"]


def test_cannot_classify_without_actual_stage_evidence():
    experiment = StrategyLabExperiment("test", build_shauli_protocol())
    with pytest.raises(ValueError):
        reject_stage(experiment, {"failed": False})
    with pytest.raises(ValueError):
        reject_stage(replace(experiment, stage=ExperimentStage.DEVELOPMENT), {"failed": False})
