from decimal import Decimal

import pytest

from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
    ProtectiveStopEvidence,
    classify_new_buy,
)


def test_new_buy_without_approved_numeric_stop_is_research_only() -> None:
    assert classify_new_buy(None) == (
        ExecutionReadiness.RESEARCH_ONLY,
        ExecutionReadinessReason.NO_APPROVED_LOSS_CONTROL_POLICY,
    )


def test_actionable_buy_requires_complete_positive_numeric_stop_evidence() -> None:
    evidence = ProtectiveStopEvidence(
        "atr-stop-2-5",
        Decimal("95"),
        Decimal("5"),
        Decimal("5"),
        "INTRADAY_TOUCH",
        "ema20-pullback-v1",
        1,
        "PAPER_FORWARD_CANDIDATE",
        True,
    )
    assert classify_new_buy(evidence)[0] == ExecutionReadiness.ACTIONABLE
    with pytest.raises(ValueError):
        ProtectiveStopEvidence(
            "atr-stop-2-5",
            Decimal("0"),
            Decimal("5"),
            Decimal("5"),
            "INTRADAY_TOUCH",
            "ema20-pullback-v1",
            1,
            "PAPER_FORWARD_CANDIDATE",
            True,
        )
