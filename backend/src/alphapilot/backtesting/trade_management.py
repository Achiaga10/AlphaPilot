from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class ProtectiveStopPolicyName(StrEnum):
    CONTROL = "control"
    ATR_STOP_1_5 = "atr-stop-1-5"
    ATR_STOP_2_0 = "atr-stop-2-0"
    ATR_STOP_3_0 = "atr-stop-3-0"

    @property
    def atr_multiple(self) -> Decimal | None:
        return {
            self.CONTROL: None,
            self.ATR_STOP_1_5: Decimal("1.5"),
            self.ATR_STOP_2_0: Decimal("2"),
            self.ATR_STOP_3_0: Decimal("3"),
        }[self]


class TrailingStopPolicyName(StrEnum):
    NONE = "none"
    ATR_TRAILING_2_0 = "atr-trailing-2-0"
    ATR_TRAILING_3_0 = "atr-trailing-3-0"

    @property
    def atr_multiple(self) -> Decimal | None:
        return {
            self.NONE: None,
            self.ATR_TRAILING_2_0: Decimal("2"),
            self.ATR_TRAILING_3_0: Decimal("3"),
        }[self]


class ProfitManagementPolicyName(StrEnum):
    NONE = "none"
    PARTIAL_2R = "partial-2r"
    FULL_3R = "full-3r"


class TradeManagementExitReason(StrEnum):
    STRATEGY_EXIT = "STRATEGY_EXIT"
    INITIAL_ATR_STOP = "INITIAL_ATR_STOP"
    ATR_TRAILING_STOP = "ATR_TRAILING_STOP"
    PARTIAL_PROFIT_2R = "PARTIAL_PROFIT_2R"
    FULL_PROFIT_3R = "FULL_PROFIT_3R"
    FINAL_OPEN_POSITION = "FINAL_OPEN_POSITION"


@dataclass(slots=True, frozen=True)
class TradeManagementConfig:
    protective_stop: ProtectiveStopPolicyName = ProtectiveStopPolicyName.CONTROL
    trailing_stop: TrailingStopPolicyName = TrailingStopPolicyName.NONE
    profit_management: ProfitManagementPolicyName = ProfitManagementPolicyName.NONE
    atr_period: int = 14

    def __post_init__(self) -> None:
        if self.atr_period != 14:
            raise ValueError("Sprint 12 trade-management ATR period must be 14")
        if self.protective_stop == ProtectiveStopPolicyName.CONTROL and (
            self.trailing_stop != TrailingStopPolicyName.NONE
            or self.profit_management != ProfitManagementPolicyName.NONE
        ):
            raise ValueError("trailing/profit management requires a protective ATR stop")
        if (
            self.trailing_stop != TrailingStopPolicyName.NONE
            and self.profit_management != ProfitManagementPolicyName.NONE
        ):
            raise ValueError("Sprint 12 permits at most one additional exit overlay")

    @property
    def requires_atr(self) -> bool:
        return self.protective_stop != ProtectiveStopPolicyName.CONTROL


@dataclass(slots=True, frozen=True)
class TradeManagementAction:
    reason: TradeManagementExitReason
    reference_price: Decimal
    shares: int
    gap_through_stop: bool = False
    closes_position: bool = True


class TradeManagementPolicy(Protocol):
    config: TradeManagementConfig

    def initial_stop(self, *, entry_price: Decimal, atr: Decimal | None) -> Decimal | None: ...

    def profit_target(
        self, *, entry_price: Decimal, initial_stop: Decimal | None
    ) -> Decimal | None: ...

    def next_effective_stop(
        self,
        *,
        initial_stop: Decimal | None,
        previous_effective_stop: Decimal | None,
        highest_completed_close: Decimal,
        atr_through_close: Decimal | None,
    ) -> Decimal | None: ...

    def evaluate(
        self,
        *,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        effective_stop: Decimal | None,
        initial_stop: Decimal | None,
        profit_target: Decimal | None,
        shares: int,
        partial_profit_taken: bool,
    ) -> TradeManagementAction | None: ...


class ConfiguredTradeManagementPolicy:
    """Deterministic daily-OHLC implementation of the frozen Sprint 12 policies."""

    def __init__(self, config: TradeManagementConfig) -> None:
        self.config = config

    def initial_stop(self, *, entry_price: Decimal, atr: Decimal | None) -> Decimal | None:
        multiple = self.config.protective_stop.atr_multiple
        if multiple is None or atr is None or atr <= 0:
            return None
        stop = entry_price - multiple * atr
        return stop if stop > 0 else None

    def profit_target(
        self, *, entry_price: Decimal, initial_stop: Decimal | None
    ) -> Decimal | None:
        if initial_stop is None:
            return None
        risk = entry_price - initial_stop
        if risk <= 0:
            return None
        if self.config.profit_management == ProfitManagementPolicyName.PARTIAL_2R:
            return entry_price + Decimal("2") * risk
        if self.config.profit_management == ProfitManagementPolicyName.FULL_3R:
            return entry_price + Decimal("3") * risk
        return None

    def next_effective_stop(
        self,
        *,
        initial_stop: Decimal | None,
        previous_effective_stop: Decimal | None,
        highest_completed_close: Decimal,
        atr_through_close: Decimal | None,
    ) -> Decimal | None:
        floor = self._maximum(initial_stop, previous_effective_stop)
        multiple = self.config.trailing_stop.atr_multiple
        if multiple is None or atr_through_close is None or atr_through_close <= 0:
            return floor
        candidate = highest_completed_close - multiple * atr_through_close
        return self._maximum(floor, candidate)

    def evaluate(
        self,
        *,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        effective_stop: Decimal | None,
        initial_stop: Decimal | None,
        profit_target: Decimal | None,
        shares: int,
        partial_profit_taken: bool,
    ) -> TradeManagementAction | None:
        if shares <= 0:
            return None

        if effective_stop is not None and open_price <= effective_stop:
            return TradeManagementAction(
                reason=self._stop_reason(effective_stop, initial_stop),
                reference_price=open_price,
                shares=shares,
                gap_through_stop=True,
            )

        target_action = self._target_action(
            open_price=open_price,
            profit_target=profit_target,
            shares=shares,
            partial_profit_taken=partial_profit_taken,
        )
        if target_action is not None and open_price >= target_action.reference_price:
            return TradeManagementAction(
                reason=target_action.reason,
                reference_price=open_price,
                shares=target_action.shares,
                closes_position=target_action.closes_position,
            )

        # Daily OHLC cannot reveal whether an intraday stop or target happened
        # first. The frozen research protocol conservatively executes the stop.
        if effective_stop is not None and low_price <= effective_stop:
            return TradeManagementAction(
                reason=self._stop_reason(effective_stop, initial_stop),
                reference_price=effective_stop,
                shares=shares,
            )

        if target_action is not None and high_price >= target_action.reference_price:
            return target_action
        return None

    def _target_action(
        self,
        *,
        open_price: Decimal,
        profit_target: Decimal | None,
        shares: int,
        partial_profit_taken: bool,
    ) -> TradeManagementAction | None:
        del open_price
        if profit_target is None:
            return None
        if self.config.profit_management == ProfitManagementPolicyName.PARTIAL_2R:
            if partial_profit_taken:
                return None
            shares_to_sell = shares // 2
            if shares_to_sell <= 0:
                return None
            return TradeManagementAction(
                reason=TradeManagementExitReason.PARTIAL_PROFIT_2R,
                reference_price=profit_target,
                shares=shares_to_sell,
                closes_position=False,
            )
        if self.config.profit_management == ProfitManagementPolicyName.FULL_3R:
            return TradeManagementAction(
                reason=TradeManagementExitReason.FULL_PROFIT_3R,
                reference_price=profit_target,
                shares=shares,
            )
        return None

    @staticmethod
    def _maximum(left: Decimal | None, right: Decimal | None) -> Decimal | None:
        values = [value for value in (left, right) if value is not None]
        return max(values) if values else None

    @staticmethod
    def _stop_reason(
        effective_stop: Decimal, initial_stop: Decimal | None
    ) -> TradeManagementExitReason:
        if initial_stop is not None and effective_stop > initial_stop:
            return TradeManagementExitReason.ATR_TRAILING_STOP
        return TradeManagementExitReason.INITIAL_ATR_STOP
