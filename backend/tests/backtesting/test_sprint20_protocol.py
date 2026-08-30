import pytest

from alphapilot.backtesting.sprint12_protocol import (
    Sprint12ExitConfiguration,
    Sprint12ResearchStage,
    validate_stage_configurations,
)
from alphapilot.strategy.name import StrategyName


def test_sprint20_new_declared_static_atr_candidates_parse_exactly() -> None:
    assert (
        Sprint12ExitConfiguration.parse_sprint20(
            "atr-stop-1-0"
        ).trade_management.protective_stop.atr_multiple
        == 1
    )
    assert (
        Sprint12ExitConfiguration.parse_sprint20(
            "atr-stop-2-5"
        ).trade_management.protective_stop.atr_multiple
        == 2.5
    )


def test_sprint20_validation_requires_control_and_one_frozen_candidate() -> None:
    valid = tuple(
        Sprint12ExitConfiguration.parse_sprint20(item) for item in ("control", "atr-stop-2-5")
    )
    validate_stage_configurations(
        stage=Sprint12ResearchStage.SPRINT20_VALIDATION,
        strategy=StrategyName.EMA20_PULLBACK,
        configurations=valid,
    )
    with pytest.raises(ValueError, match="control followed"):
        validate_stage_configurations(
            stage=Sprint12ResearchStage.SPRINT20_VALIDATION,
            strategy=StrategyName.EMA20_PULLBACK,
            configurations=valid[::-1],
        )
