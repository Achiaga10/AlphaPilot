from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioDecision,
    PortfolioStatePosition,
)
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import PortfolioDecisionType, SizingPolicyName


class PlanActionApplyReason(StrEnum):
    READY = "READY"
    APPLIED = "APPLIED"
    ACTION_NOT_APPROVED = "ACTION_NOT_APPROVED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    PRIOR_ACTION_REQUIRED = "PRIOR_ACTION_REQUIRED"
    INSUFFICIENT_CURRENT_DRAFT_CASH = "INSUFFICIENT_CURRENT_DRAFT_CASH"
    POSITION_ALREADY_HELD = "POSITION_ALREADY_HELD"
    POSITION_NOT_HELD = "POSITION_NOT_HELD"
    CURRENT_DRAFT_POSITION_CHANGED = "CURRENT_DRAFT_POSITION_CHANGED"
    INVALID_SHARE_QUANTITY = "INVALID_SHARE_QUANTITY"
    MAX_POSITIONS = "MAX_POSITIONS"
    MAX_POSITION_WEIGHT = "MAX_POSITION_WEIGHT"
    CASH_RESERVE = "CASH_RESERVE"
    SECTOR_LIMIT = "SECTOR_LIMIT"
    PORTFOLIO_RISK_LIMIT = "PORTFOLIO_RISK_LIMIT"
    INVALID_RISK_DISTANCE = "INVALID_RISK_DISTANCE"


class PlanActionQuantitySemantics(StrEnum):
    SAME_PLAN_ACTION = "SAME_PLAN_ACTION"
    CURRENT_REVALIDATED_RECOMMENDATION = "CURRENT_REVALIDATED_RECOMMENDATION"
    USER_QUANTITY_OVERRIDE = "USER_QUANTITY_OVERRIDE"


class PlanActionValidationStatus(StrEnum):
    VALID = "VALID"
    REJECTED = "REJECTED"


@dataclass(slots=True, frozen=True)
class PlanActionApplyResult:
    applied: bool
    reason: PlanActionApplyReason
    action_id: str | None
    action_type: PortfolioDecisionType
    cash_before: Decimal
    cash_impact: Decimal
    cash_after: Decimal
    position_before: PortfolioStatePosition | None
    position_after: PortfolioStatePosition | None
    portfolio: CurrentPortfolioState
    validation_status: PlanActionValidationStatus
    quantity_semantics: PlanActionQuantitySemantics
    recommended_shares: int
    requested_shares: int
    recommended_allocation_dollars: Decimal
    requested_allocation_dollars: Decimal
    resulting_position_weight_pct: Decimal
    sector_weight_before_pct: Decimal
    sector_weight_after_pct: Decimal
    modeled_position_risk_dollars: Decimal | None
    portfolio_risk_after_dollars: Decimal | None
    cash_reserve_requirement: Decimal | None


class PortfolioPlanActionService:
    """Apply one approved plan action to a supplied research draft."""

    def apply(
        self,
        *,
        state: CurrentPortfolioState,
        decision: PortfolioDecision,
        applied_action_ids: frozenset[str],
        requested_shares: int | None = None,
        config: PortfolioRiskConfig | None = None,
        sizing_policy: SizingPolicyName = SizingPolicyName.ATR_RISK,
        apply: bool = True,
    ) -> PlanActionApplyResult:
        risk_config = config or PortfolioRiskConfig()
        action_id = decision.action_id
        if decision.decision not in {PortfolioDecisionType.BUY, PortfolioDecisionType.SELL}:
            return self._rejected(state, decision, PlanActionApplyReason.ACTION_NOT_APPROVED)
        if action_id is None:
            return self._rejected(state, decision, PlanActionApplyReason.ACTION_NOT_APPROVED)
        if action_id in applied_action_ids:
            return self._rejected(state, decision, PlanActionApplyReason.ALREADY_APPLIED)
        if not set(decision.depends_on_action_ids).issubset(applied_action_ids):
            return self._rejected(state, decision, PlanActionApplyReason.PRIOR_ACTION_REQUIRED)

        positions = {item.ticker.upper(): item for item in state.positions}
        ticker = decision.ticker.upper()
        held = positions.get(ticker)
        if decision.decision == PortfolioDecisionType.BUY:
            if held is not None:
                return self._rejected(
                    state, decision, PlanActionApplyReason.POSITION_ALREADY_HELD, held
                )
            equity = state.equity
            if len(state.positions) >= risk_config.max_positions:
                return self._rejected(state, decision, PlanActionApplyReason.MAX_POSITIONS)
            current_recommendation = self._current_recommended_shares(
                state=state,
                decision=decision,
                config=risk_config,
                sizing_policy=sizing_policy,
            )
            recommended_shares = current_recommendation or decision.proposed_shares
            shares = recommended_shares if requested_shares is None else requested_shares
            if decision.proposed_shares <= 0 or shares <= 0:
                return self._rejected(state, decision, PlanActionApplyReason.INVALID_SHARE_QUANTITY)
            outlay = Decimal(shares) * decision.reference_price
            semantics = (
                PlanActionQuantitySemantics.SAME_PLAN_ACTION
                if shares == decision.proposed_shares
                and recommended_shares == decision.proposed_shares
                else PlanActionQuantitySemantics.CURRENT_REVALIDATED_RECOMMENDATION
                if requested_shares is None
                else PlanActionQuantitySemantics.USER_QUANTITY_OVERRIDE
            )
            sector_before_value = sum(
                (
                    item.market_value
                    for item in state.positions
                    if self._sector(item.sector) == self._sector(decision.sector)
                ),
                Decimal("0"),
            )
            weight_pct = self._pct(outlay, equity)
            sector_before_pct = self._pct(sector_before_value, equity)
            sector_after_pct = self._pct(sector_before_value + outlay, equity)
            if state.cash < outlay:
                return self._rejected(
                    state,
                    decision,
                    PlanActionApplyReason.INSUFFICIENT_CURRENT_DRAFT_CASH,
                    metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                )
            if weight_pct > risk_config.max_position_weight_pct:
                return self._rejected(
                    state,
                    decision,
                    PlanActionApplyReason.MAX_POSITION_WEIGHT,
                    metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                )
            if sector_after_pct > risk_config.max_sector_weight_pct:
                return self._rejected(
                    state,
                    decision,
                    PlanActionApplyReason.SECTOR_LIMIT,
                    metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                )
            stop_distance: Decimal | None = None
            modeled_risk: Decimal | None = None
            portfolio_risk_after: Decimal | None = None
            reserve: Decimal | None = None
            if sizing_policy != SizingPolicyName.EQUAL_SLOT:
                reserve = equity * risk_config.minimum_cash_reserve_pct / Decimal("100")
                if state.cash - outlay < reserve:
                    return self._rejected(
                        state,
                        decision,
                        PlanActionApplyReason.CASH_RESERVE,
                        metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                        reserve=reserve,
                    )
                if decision.atr is None:
                    return self._rejected(
                        state,
                        decision,
                        PlanActionApplyReason.INVALID_RISK_DISTANCE,
                        metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                        reserve=reserve,
                    )
                stop_distance = decision.atr * risk_config.atr_stop_multiple
                if stop_distance <= 0:
                    return self._rejected(
                        state,
                        decision,
                        PlanActionApplyReason.INVALID_RISK_DISTANCE,
                        metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                        reserve=reserve,
                    )
                modeled_risk = Decimal(shares) * stop_distance
                current_risk = sum(
                    (item.modeled_risk_dollars for item in state.positions), Decimal("0")
                )
                portfolio_risk_after = current_risk + modeled_risk
                risk_limit = equity * risk_config.max_portfolio_risk_pct / Decimal("100")
                if portfolio_risk_after > risk_limit:
                    return self._rejected(
                        state,
                        decision,
                        PlanActionApplyReason.PORTFOLIO_RISK_LIMIT,
                        metrics=(shares, outlay, weight_pct, sector_before_pct, sector_after_pct),
                        modeled_risk=modeled_risk,
                        portfolio_risk_after=portfolio_risk_after,
                        reserve=reserve,
                    )
            position = PortfolioStatePosition(
                ticker=ticker,
                shares=shares,
                reference_price=decision.reference_price,
                cost_basis=decision.reference_price,
                sector=decision.sector,
                modeled_risk_dollars=modeled_risk or Decimal("0"),
            )
            updated = CurrentPortfolioState(
                cash=state.cash - outlay,
                positions=tuple((*state.positions, position)),
            )
            return PlanActionApplyResult(
                applied=apply,
                reason=PlanActionApplyReason.APPLIED if apply else PlanActionApplyReason.READY,
                action_id=action_id,
                action_type=decision.decision,
                cash_before=state.cash,
                cash_impact=-outlay,
                cash_after=updated.cash,
                position_before=None,
                position_after=position,
                portfolio=updated if apply else state,
                validation_status=PlanActionValidationStatus.VALID,
                quantity_semantics=semantics,
                recommended_shares=recommended_shares,
                requested_shares=shares,
                recommended_allocation_dollars=(
                    Decimal(recommended_shares) * decision.reference_price
                ),
                requested_allocation_dollars=outlay,
                resulting_position_weight_pct=weight_pct,
                sector_weight_before_pct=sector_before_pct,
                sector_weight_after_pct=sector_after_pct,
                modeled_position_risk_dollars=modeled_risk,
                portfolio_risk_after_dollars=portfolio_risk_after,
                cash_reserve_requirement=reserve,
            )

        if held is None:
            return self._rejected(state, decision, PlanActionApplyReason.POSITION_NOT_HELD)
        if held.shares != decision.current_shares:
            return self._rejected(
                state,
                decision,
                PlanActionApplyReason.CURRENT_DRAFT_POSITION_CHANGED,
                held,
            )
        proceeds = decision.estimated_proceeds
        if proceeds is None or proceeds < 0:
            return self._rejected(state, decision, PlanActionApplyReason.ACTION_NOT_APPROVED, held)
        updated = CurrentPortfolioState(
            cash=state.cash + proceeds,
            positions=tuple(item for item in state.positions if item.ticker.upper() != ticker),
        )
        return PlanActionApplyResult(
            applied=apply,
            reason=PlanActionApplyReason.APPLIED if apply else PlanActionApplyReason.READY,
            action_id=action_id,
            action_type=decision.decision,
            cash_before=state.cash,
            cash_impact=proceeds,
            cash_after=updated.cash,
            position_before=held,
            position_after=None,
            portfolio=updated if apply else state,
            validation_status=PlanActionValidationStatus.VALID,
            quantity_semantics=PlanActionQuantitySemantics.SAME_PLAN_ACTION,
            recommended_shares=decision.current_shares,
            requested_shares=decision.current_shares,
            recommended_allocation_dollars=proceeds,
            requested_allocation_dollars=proceeds,
            resulting_position_weight_pct=Decimal("0"),
            sector_weight_before_pct=Decimal("0"),
            sector_weight_after_pct=Decimal("0"),
            modeled_position_risk_dollars=None,
            portfolio_risk_after_dollars=None,
            cash_reserve_requirement=None,
        )

    @staticmethod
    def _current_recommended_shares(
        *,
        state: CurrentPortfolioState,
        decision: PortfolioDecision,
        config: PortfolioRiskConfig,
        sizing_policy: SizingPolicyName,
    ) -> int:
        if decision.reference_price <= 0 or decision.proposed_shares <= 0:
            return 0
        equity = state.equity
        price = decision.reference_price
        limits = [
            decision.proposed_shares,
            int(state.cash // price),
            int((equity * config.max_position_weight_pct / Decimal("100")) // price),
        ]
        sector_value = sum(
            (
                item.market_value
                for item in state.positions
                if PortfolioPlanActionService._sector(item.sector)
                == PortfolioPlanActionService._sector(decision.sector)
            ),
            Decimal("0"),
        )
        sector_capacity = equity * config.max_sector_weight_pct / Decimal("100") - sector_value
        limits.append(max(0, int(sector_capacity // price)))
        if sizing_policy != SizingPolicyName.EQUAL_SLOT:
            reserve = equity * config.minimum_cash_reserve_pct / Decimal("100")
            limits.append(max(0, int((state.cash - reserve) // price)))
            if decision.atr is not None and decision.atr > 0:
                stop_distance = decision.atr * config.atr_stop_multiple
                current_risk = sum(
                    (item.modeled_risk_dollars for item in state.positions), Decimal("0")
                )
                risk_capacity = (
                    equity * config.max_portfolio_risk_pct / Decimal("100") - current_risk
                )
                limits.append(max(0, int(risk_capacity // stop_distance)))
        return max(0, min(limits))

    @staticmethod
    def _rejected(
        state: CurrentPortfolioState,
        decision: PortfolioDecision,
        reason: PlanActionApplyReason,
        held: PortfolioStatePosition | None = None,
        metrics: tuple[int, Decimal, Decimal, Decimal, Decimal] | None = None,
        modeled_risk: Decimal | None = None,
        portfolio_risk_after: Decimal | None = None,
        reserve: Decimal | None = None,
    ) -> PlanActionApplyResult:
        shares, allocation, weight, sector_before, sector_after = metrics or (
            0,
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
        )
        return PlanActionApplyResult(
            applied=False,
            reason=reason,
            action_id=decision.action_id,
            action_type=decision.decision,
            cash_before=state.cash,
            cash_impact=Decimal("0"),
            cash_after=state.cash,
            position_before=held,
            position_after=held,
            portfolio=state,
            validation_status=PlanActionValidationStatus.REJECTED,
            quantity_semantics=(
                PlanActionQuantitySemantics.SAME_PLAN_ACTION
                if shares in {0, decision.proposed_shares}
                else PlanActionQuantitySemantics.USER_QUANTITY_OVERRIDE
            ),
            recommended_shares=decision.proposed_shares,
            requested_shares=shares,
            recommended_allocation_dollars=decision.target_allocation_dollars,
            requested_allocation_dollars=allocation,
            resulting_position_weight_pct=weight,
            sector_weight_before_pct=sector_before,
            sector_weight_after_pct=sector_after,
            modeled_position_risk_dollars=modeled_risk,
            portfolio_risk_after_dollars=portfolio_risk_after,
            cash_reserve_requirement=reserve,
        )

    @staticmethod
    def _pct(value: Decimal, equity: Decimal) -> Decimal:
        return value / equity * Decimal("100") if equity > 0 else Decimal("0")

    @staticmethod
    def _sector(value: str | None) -> str:
        return value.strip() if value and value.strip() else "Unclassified"


class ManualSellReason(StrEnum):
    READY = "READY"
    APPLIED = "APPLIED"
    POSITION_NOT_HELD = "POSITION_NOT_HELD"
    INVALID_SHARE_QUANTITY = "INVALID_SHARE_QUANTITY"
    STORED_PRICE_UNAVAILABLE = "STORED_PRICE_UNAVAILABLE"


class ManualSellPriceSource(StrEnum):
    LATEST_STORED_CANDLE = "LATEST_STORED_CANDLE"
    USER_PROVIDED = "USER_PROVIDED"


class LatestStoredPriceLookup(Protocol):
    async def get_latest_stored_price(self, ticker: str) -> tuple[Decimal, date] | None: ...


@dataclass(slots=True, frozen=True)
class ManualSellResult:
    applied: bool
    reason: ManualSellReason
    ticker: str
    shares_sold: int
    shares_remaining: int
    execution_price: Decimal | None
    price_source: ManualSellPriceSource | None
    price_date: date | None
    gross_proceeds: Decimal
    cash_before: Decimal
    cash_after: Decimal
    position_removed: bool
    portfolio: CurrentPortfolioState


class ManualPortfolioSellService:
    def __init__(self, prices: LatestStoredPriceLookup) -> None:
        self.prices = prices

    async def sell(
        self,
        *,
        state: CurrentPortfolioState,
        ticker: str,
        shares_to_sell: int,
        execution_price: Decimal | None,
        apply: bool,
    ) -> ManualSellResult:
        normalized = ticker.strip().upper()
        held = next((item for item in state.positions if item.ticker.upper() == normalized), None)
        if held is None:
            return self._rejected(state, normalized, ManualSellReason.POSITION_NOT_HELD)
        if shares_to_sell <= 0 or shares_to_sell > held.shares:
            return self._rejected(
                state, normalized, ManualSellReason.INVALID_SHARE_QUANTITY, held.shares
            )

        stored = await self.prices.get_latest_stored_price(normalized)
        price_date: date | None
        if execution_price is None:
            if stored is None:
                return self._rejected(
                    state, normalized, ManualSellReason.STORED_PRICE_UNAVAILABLE, held.shares
                )
            used_price, price_date = stored
            source = ManualSellPriceSource.LATEST_STORED_CANDLE
        else:
            used_price = execution_price
            price_date = None
            source = ManualSellPriceSource.USER_PROVIDED

        proceeds = Decimal(shares_to_sell) * used_price
        remaining = held.shares - shares_to_sell
        position_after = (
            None
            if remaining == 0
            else PortfolioStatePosition(
                ticker=held.ticker,
                shares=remaining,
                reference_price=held.reference_price,
                cost_basis=held.cost_basis,
                sector=held.sector,
                modeled_risk_dollars=(
                    held.modeled_risk_dollars * Decimal(remaining) / Decimal(held.shares)
                ),
            )
        )
        positions = tuple(item for item in state.positions if item.ticker.upper() != normalized) + (
            (position_after,) if position_after is not None else ()
        )
        updated = CurrentPortfolioState(
            cash=state.cash + proceeds,
            positions=positions,
        )
        return ManualSellResult(
            applied=apply,
            reason=ManualSellReason.APPLIED if apply else ManualSellReason.READY,
            ticker=normalized,
            shares_sold=shares_to_sell,
            shares_remaining=remaining,
            execution_price=used_price,
            price_source=source,
            price_date=price_date,
            gross_proceeds=proceeds,
            cash_before=state.cash,
            cash_after=updated.cash,
            position_removed=remaining == 0,
            portfolio=updated,
        )

    @staticmethod
    def _rejected(
        state: CurrentPortfolioState,
        ticker: str,
        reason: ManualSellReason,
        shares_remaining: int = 0,
    ) -> ManualSellResult:
        return ManualSellResult(
            applied=False,
            reason=reason,
            ticker=ticker,
            shares_sold=0,
            shares_remaining=shares_remaining,
            execution_price=None,
            price_source=None,
            price_date=None,
            gross_proceeds=Decimal("0"),
            cash_before=state.cash,
            cash_after=state.cash,
            position_removed=False,
            portfolio=state,
        )
