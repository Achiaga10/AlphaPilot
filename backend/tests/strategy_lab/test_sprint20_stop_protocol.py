from decimal import Decimal

from alphapilot.strategy.name import StrategyName
from alphapilot.strategy_lab.identity import experiment_identity
from alphapilot.strategy_lab.sprint20_stop_protocol import (
    RelativeStopMetrics,
    build_round2_ema_protocol,
    build_stop_protocol,
    passes_development_gates,
    passes_validation_gates,
)


def test_sprint20_protocol_is_closed_snapshot_bound_and_deterministic() -> None:
    first = build_stop_protocol(StrategyName.EMA20_PULLBACK)
    second = build_stop_protocol(StrategyName.EMA20_PULLBACK)
    assert experiment_identity(first) == experiment_identity(second)
    assert [item.label for item in first.candidates] == [
        "control",
        "atr-stop-2-0",
        "atr-stop-2-5",
        "atr-stop-3-0",
    ]
    assert first.dataset is not None and first.dataset.finalized


def test_sprint20_gate_failure_produces_no_implicit_fallback() -> None:
    weak = RelativeStopMetrics(
        Decimal("74.9"), Decimal("0"), Decimal("100"), Decimal("100"), Decimal("0"), Decimal("100")
    )
    assert not passes_development_gates(weak)
    validation = RelativeStopMetrics(
        Decimal("100"),
        Decimal("0"),
        Decimal("100"),
        Decimal("100"),
        Decimal("0"),
        Decimal("100"),
        folds_return_better_or_equal=1,
        folds_sharpe_better_or_equal=3,
        folds_drawdown_better_or_equal=3,
    )
    assert not passes_validation_gates(validation)


def test_round2_protocol_is_closed_and_structurally_distinct() -> None:
    protocol = build_round2_ema_protocol()
    assert [item.label for item in protocol.candidates] == [
        "control",
        "atr-stop-2-0",
        "signal-day-low-invalidation",
    ]
    assert experiment_identity(protocol) == experiment_identity(build_round2_ema_protocol())
