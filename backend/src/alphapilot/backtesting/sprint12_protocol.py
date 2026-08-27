from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from alphapilot.backtesting.trade_management import (
    ProfitManagementPolicyName,
    ProtectiveStopPolicyName,
    TradeManagementConfig,
    TrailingStopPolicyName,
)
from alphapilot.strategy.name import StrategyName


class Sprint12ResearchStage(StrEnum):
    BASELINE = "baseline"
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    FOLD = "fold"


@dataclass(slots=True, frozen=True)
class FrozenExitSelection:
    protective: TradeManagementConfig
    final: TradeManagementConfig


@dataclass(slots=True, frozen=True)
class Sprint12ExitConfiguration:
    label: str
    trade_management: TradeManagementConfig

    @classmethod
    def parse(cls, value: str) -> Sprint12ExitConfiguration:
        parts = value.split("+")
        if len(parts) > 2:
            raise ValueError("configuration permits one protective stop and one overlay")

        try:
            protective = ProtectiveStopPolicyName(parts[0])
        except ValueError as exc:
            raise ValueError(f"undeclared Sprint 12 protective stop: {parts[0]}") from exc

        trailing = TrailingStopPolicyName.NONE
        profit = ProfitManagementPolicyName.NONE
        if len(parts) == 2:
            overlay = parts[1]
            try:
                trailing = TrailingStopPolicyName(overlay)
            except ValueError:
                try:
                    profit = ProfitManagementPolicyName(overlay)
                except ValueError as exc:
                    raise ValueError(f"undeclared Sprint 12 exit overlay: {overlay}") from exc
            if (
                trailing == TrailingStopPolicyName.NONE
                and profit == ProfitManagementPolicyName.NONE
            ):
                raise ValueError("configuration overlay cannot be none")

        trade_management = TradeManagementConfig(
            protective_stop=protective,
            trailing_stop=trailing,
            profit_management=profit,
        )
        return cls(label=value, trade_management=trade_management)


# Frozen from development before validation. Neither strategy selected an
# additional trailing/profit overlay, so protective and final are identical.
FROZEN_EXIT_SELECTIONS: dict[StrategyName, FrozenExitSelection] = {
    StrategyName.EMA20_PULLBACK: FrozenExitSelection(
        protective=TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.ATR_STOP_3_0,
        ),
        final=TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.ATR_STOP_3_0,
        ),
    ),
    StrategyName.MICHO_150: FrozenExitSelection(
        protective=TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.ATR_STOP_1_5,
        ),
        final=TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.ATR_STOP_1_5,
        ),
    ),
}


def validate_stage_configurations(
    *,
    stage: Sprint12ResearchStage,
    strategy: StrategyName,
    configurations: tuple[Sprint12ExitConfiguration, ...],
    frozen_selections: dict[StrategyName, FrozenExitSelection] | None = None,
) -> None:
    if not configurations:
        raise ValueError("at least one exit configuration is required")
    if len({item.label for item in configurations}) != len(configurations):
        raise ValueError("duplicate exit configurations are not permitted")
    if stage in (Sprint12ResearchStage.BASELINE, Sprint12ResearchStage.DEVELOPMENT):
        return

    frozen = (frozen_selections or FROZEN_EXIT_SELECTIONS).get(strategy)
    if frozen is None:
        raise ValueError(
            f"{strategy.value} development selection must be frozen before {stage.value}"
        )
    expected = {
        TradeManagementConfig(),
        frozen.protective,
        frozen.final,
    }
    actual = {item.trade_management for item in configurations}
    if actual != expected:
        raise ValueError(
            "validation/fold configuration set does not exactly match frozen development selection"
        )


def default_sizing_policy_value(strategy: StrategyName) -> str:
    return "equal-slot" if strategy == StrategyName.EMA20_PULLBACK else "atr-volatility-normalized"
