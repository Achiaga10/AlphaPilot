from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from alphapilot.portfolio.risk import PortfolioRiskConfig


class SizingPolicyName(StrEnum):
    EQUAL_SLOT = "equal-slot"
    ATR_RISK = "atr-risk"
    ATR_VOLATILITY_NORMALIZED = "atr-volatility-normalized"


class PortfolioDecisionType(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    SKIP = "SKIP"


class PortfolioDecisionReason(StrEnum):
    BUY_APPROVED = "BUY_APPROVED"
    SELL_APPROVED = "SELL_APPROVED"
    ALREADY_HELD = "ALREADY_HELD"
    NO_POSITION_TO_SELL = "NO_POSITION_TO_SELL"
    MAX_POSITIONS = "MAX_POSITIONS"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    CASH_RESERVE = "CASH_RESERVE"
    MAX_POSITION_WEIGHT = "MAX_POSITION_WEIGHT"
    PORTFOLIO_RISK_LIMIT = "PORTFOLIO_RISK_LIMIT"
    SECTOR_LIMIT = "SECTOR_LIMIT"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID_RISK_DISTANCE = "INVALID_RISK_DISTANCE"
    RANKING_NOT_SELECTED = "RANKING_NOT_SELECTED"
    INSUFFICIENT_ALLOCATION = "INSUFFICIENT_ALLOCATION"
    STALE_DATA = "STALE_DATA"
    NO_ACTION = "NO_ACTION"
    NEWS_RISK_BLOCK = "NEWS_RISK_BLOCK"
    NEWS_ASSESSMENT_UNAVAILABLE = "NEWS_ASSESSMENT_UNAVAILABLE"
    NEWS_RISK_EXIT = "NEWS_RISK_EXIT"
    ENTRY_TOO_EXTENDED_ABOVE_EMA20 = "ENTRY_TOO_EXTENDED_ABOVE_EMA20"
    EMA20_ENTRY_REVALIDATION_UNAVAILABLE = "EMA20_ENTRY_REVALIDATION_UNAVAILABLE"


@dataclass(slots=True, frozen=True)
class SizingContext:
    equity: Decimal
    cash: Decimal
    execution_price: Decimal
    atr: Decimal | None
    current_portfolio_risk: Decimal
    sector_market_value: Decimal
    commission: Decimal = Decimal("0")


@dataclass(slots=True, frozen=True)
class SizingDecision:
    shares: int
    reason: PortfolioDecisionReason
    atr: Decimal | None
    stop_distance: Decimal | None
    risk_budget: Decimal
    allocation: Decimal
    position_weight_pct: Decimal
    modeled_risk: Decimal
    cash_reserve: Decimal
    sector_weight_before_pct: Decimal
    sector_weight_after_pct: Decimal
    normalized_sizing_weight: Decimal | None = None


@dataclass(slots=True, frozen=True)
class VolatilitySizingCandidate:
    ticker: str
    execution_price: Decimal
    atr: Decimal | None
    sector: str


@dataclass(slots=True, frozen=True)
class VolatilityBatchContext:
    equity: Decimal
    cash: Decimal
    invested_value: Decimal
    current_portfolio_risk: Decimal
    sector_market_values: dict[str, Decimal]
    available_slots: int
    commission: Decimal = Decimal("0")


@dataclass(slots=True, frozen=True)
class VolatilityBatchAllocation:
    ticker: str
    normalized_weight: Decimal | None
    decision: SizingDecision


class AtrRiskPositionSizer:
    PCT = Decimal("100")

    def size(self, context: SizingContext, config: PortfolioRiskConfig) -> SizingDecision:
        reserve = context.equity * config.minimum_cash_reserve_pct / self.PCT
        before = self._pct(context.sector_market_value, context.equity)
        risk_budget = context.equity * config.risk_per_position_pct / self.PCT
        empty = self._decision(
            0,
            PortfolioDecisionReason.INSUFFICIENT_HISTORY,
            context,
            None,
            reserve,
            before,
            risk_budget,
        )
        if context.atr is None:
            return empty
        stop_distance = context.atr * config.atr_stop_multiple
        if stop_distance <= 0 or context.execution_price <= 0:
            return self._decision(
                0,
                PortfolioDecisionReason.INVALID_RISK_DISTANCE,
                context,
                stop_distance,
                reserve,
                before,
                risk_budget,
            )
        risk_shares = int(risk_budget / stop_distance)
        weight_dollars = context.equity * config.max_position_weight_pct / self.PCT
        weight_shares = int(weight_dollars / context.execution_price)
        entry_cash = max(context.cash - reserve - context.commission, Decimal("0"))
        cash_shares = int(entry_cash / context.execution_price)
        risk_limit = context.equity * config.max_portfolio_risk_pct / self.PCT
        remaining_risk = max(risk_limit - context.current_portfolio_risk, Decimal("0"))
        portfolio_risk_shares = int(remaining_risk / stop_distance)
        sector_limit = context.equity * config.max_sector_weight_pct / self.PCT
        sector_room = max(sector_limit - context.sector_market_value, Decimal("0"))
        sector_shares = int(sector_room / context.execution_price)
        caps = (
            (risk_shares, PortfolioDecisionReason.INVALID_RISK_DISTANCE),
            (weight_shares, PortfolioDecisionReason.MAX_POSITION_WEIGHT),
            (cash_shares, PortfolioDecisionReason.CASH_RESERVE),
            (portfolio_risk_shares, PortfolioDecisionReason.PORTFOLIO_RISK_LIMIT),
            (sector_shares, PortfolioDecisionReason.SECTOR_LIMIT),
        )
        shares = min(value for value, _ in caps)
        if shares <= 0:
            reason = next(reason for value, reason in caps if value == shares)
            if context.cash <= context.commission:
                reason = PortfolioDecisionReason.INSUFFICIENT_CASH
            return self._decision(0, reason, context, stop_distance, reserve, before, risk_budget)
        return self._decision(
            shares,
            PortfolioDecisionReason.BUY_APPROVED,
            context,
            stop_distance,
            reserve,
            before,
            risk_budget,
        )

    def _decision(
        self,
        shares: int,
        reason: PortfolioDecisionReason,
        context: SizingContext,
        stop_distance: Decimal | None,
        reserve: Decimal,
        before: Decimal,
        risk_budget: Decimal,
    ) -> SizingDecision:
        allocation = Decimal(shares) * context.execution_price
        risk = Decimal(shares) * (stop_distance or Decimal("0"))
        return SizingDecision(
            shares=shares,
            reason=reason,
            atr=context.atr,
            stop_distance=stop_distance,
            risk_budget=risk_budget,
            allocation=allocation,
            position_weight_pct=self._pct(allocation, context.equity),
            modeled_risk=risk,
            cash_reserve=reserve,
            sector_weight_before_pct=before,
            sector_weight_after_pct=self._pct(
                context.sector_market_value + allocation, context.equity
            ),
        )

    @staticmethod
    def _pct(value: Decimal, equity: Decimal) -> Decimal:
        return value / equity * Decimal("100") if equity > 0 else Decimal("0")


class EqualSlotPositionSizer:
    """Advisory equivalent of the unchanged historical equal-slot policy."""

    def size(self, context: SizingContext, config: PortfolioRiskConfig) -> SizingDecision:
        if context.execution_price <= 0:
            shares = 0
        else:
            target = context.equity / Decimal(config.max_positions)
            shares = int(
                min(target, max(context.cash - context.commission, Decimal("0")))
                / context.execution_price
            )
        allocation = Decimal(shares) * context.execution_price
        before = (
            context.sector_market_value / context.equity * Decimal("100")
            if context.equity > 0
            else Decimal("0")
        )
        after = (
            (context.sector_market_value + allocation) / context.equity * Decimal("100")
            if context.equity > 0
            else Decimal("0")
        )
        reason = (
            PortfolioDecisionReason.BUY_APPROVED
            if shares > 0
            else PortfolioDecisionReason.INSUFFICIENT_CASH
        )
        return SizingDecision(
            shares=shares,
            reason=reason,
            atr=context.atr,
            stop_distance=None,
            risk_budget=Decimal("0"),
            allocation=allocation,
            position_weight_pct=(
                allocation / context.equity * Decimal("100") if context.equity > 0 else Decimal("0")
            ),
            modeled_risk=Decimal("0"),
            cash_reserve=Decimal("0"),
            sector_weight_before_pct=before,
            sector_weight_after_pct=after,
        )


class AtrVolatilityNormalizedPositionSizer:
    """Allocates one ranked candidate group using inverse ATR percentage weights."""

    PCT = Decimal("100")

    @staticmethod
    def atr_percentage(atr: Decimal, reference_price: Decimal) -> Decimal | None:
        if atr <= 0 or reference_price <= 0:
            return None
        return atr / reference_price

    def normalized_weights(self, candidates: list[VolatilitySizingCandidate]) -> dict[str, Decimal]:
        raw_weights: dict[str, Decimal] = {}
        for candidate in candidates:
            if candidate.atr is None:
                continue
            atr_pct = self.atr_percentage(candidate.atr, candidate.execution_price)
            if atr_pct is not None:
                raw_weights[candidate.ticker] = Decimal("1") / atr_pct
        total = sum(raw_weights.values(), Decimal("0"))
        if total <= 0:
            return {}
        return {ticker: raw / total for ticker, raw in raw_weights.items()}

    def allocate(
        self,
        context: VolatilityBatchContext,
        candidates: list[VolatilitySizingCandidate],
        config: PortfolioRiskConfig,
    ) -> tuple[VolatilityBatchAllocation, ...]:
        valid = [
            candidate
            for candidate in candidates
            if candidate.atr is not None
            and self.atr_percentage(candidate.atr, candidate.execution_price) is not None
        ]
        selected = valid[: max(context.available_slots, 0)]
        weights = self.normalized_weights(selected)
        selected_tickers = {candidate.ticker for candidate in selected}
        reserve = context.equity * config.minimum_cash_reserve_pct / self.PCT
        investable_equity = context.equity - reserve
        allocatable = max(investable_equity - context.invested_value, Decimal("0"))
        allocatable = min(
            allocatable,
            max(context.cash - reserve - context.commission, Decimal("0")),
        )
        cash = context.cash
        risk = context.current_portfolio_risk
        sector_values = dict(context.sector_market_values)
        results: list[VolatilityBatchAllocation] = []

        for candidate in candidates:
            before = self._pct(sector_values.get(candidate.sector, Decimal("0")), context.equity)
            if candidate.atr is None:
                decision = self._decision(
                    candidate,
                    0,
                    PortfolioDecisionReason.INSUFFICIENT_HISTORY,
                    context.equity,
                    reserve,
                    before,
                    Decimal("0"),
                    None,
                    None,
                )
                results.append(VolatilityBatchAllocation(candidate.ticker, None, decision))
                continue
            atr_pct = self.atr_percentage(candidate.atr, candidate.execution_price)
            if atr_pct is None:
                decision = self._decision(
                    candidate,
                    0,
                    PortfolioDecisionReason.INVALID_RISK_DISTANCE,
                    context.equity,
                    reserve,
                    before,
                    Decimal("0"),
                    candidate.atr * config.atr_stop_multiple,
                    None,
                )
                results.append(VolatilityBatchAllocation(candidate.ticker, None, decision))
                continue
            if candidate.ticker not in selected_tickers:
                decision = self._decision(
                    candidate,
                    0,
                    PortfolioDecisionReason.RANKING_NOT_SELECTED,
                    context.equity,
                    reserve,
                    before,
                    Decimal("0"),
                    candidate.atr * config.atr_stop_multiple,
                    None,
                )
                results.append(VolatilityBatchAllocation(candidate.ticker, None, decision))
                continue

            normalized_weight = weights[candidate.ticker]
            target_dollars = allocatable * normalized_weight
            stop_distance = candidate.atr * config.atr_stop_multiple
            weight_cap = context.equity * config.max_position_weight_pct / self.PCT
            target_shares = int(min(target_dollars, weight_cap) / candidate.execution_price)
            cash_room = max(cash - reserve - context.commission, Decimal("0"))
            cash_shares = int(cash_room / candidate.execution_price)
            risk_limit = context.equity * config.max_portfolio_risk_pct / self.PCT
            risk_room = max(risk_limit - risk, Decimal("0"))
            risk_shares = int(risk_room / stop_distance)
            sector_limit = context.equity * config.max_sector_weight_pct / self.PCT
            sector_room = max(
                sector_limit - sector_values.get(candidate.sector, Decimal("0")),
                Decimal("0"),
            )
            sector_shares = int(sector_room / candidate.execution_price)
            caps = (
                (target_shares, PortfolioDecisionReason.INSUFFICIENT_ALLOCATION),
                (cash_shares, PortfolioDecisionReason.CASH_RESERVE),
                (risk_shares, PortfolioDecisionReason.PORTFOLIO_RISK_LIMIT),
                (sector_shares, PortfolioDecisionReason.SECTOR_LIMIT),
            )
            shares = min(value for value, _ in caps)
            if shares <= 0:
                reason = next(reason for value, reason in caps if value == shares)
                if cash <= context.commission:
                    reason = PortfolioDecisionReason.INSUFFICIENT_CASH
            else:
                reason = PortfolioDecisionReason.BUY_APPROVED
            decision = self._decision(
                candidate,
                shares,
                reason,
                context.equity,
                reserve,
                before,
                risk_room,
                stop_distance,
                normalized_weight,
            )
            results.append(VolatilityBatchAllocation(candidate.ticker, normalized_weight, decision))
            if shares > 0:
                cash -= decision.allocation + context.commission
                risk += decision.modeled_risk
                sector_values[candidate.sector] = (
                    sector_values.get(candidate.sector, Decimal("0")) + decision.allocation
                )

        return tuple(results)

    def _decision(
        self,
        candidate: VolatilitySizingCandidate,
        shares: int,
        reason: PortfolioDecisionReason,
        equity: Decimal,
        reserve: Decimal,
        before: Decimal,
        risk_budget: Decimal,
        stop_distance: Decimal | None,
        normalized_weight: Decimal | None,
    ) -> SizingDecision:
        allocation = Decimal(shares) * candidate.execution_price
        return SizingDecision(
            shares=shares,
            reason=reason,
            atr=candidate.atr,
            stop_distance=stop_distance,
            risk_budget=risk_budget,
            allocation=allocation,
            position_weight_pct=self._pct(allocation, equity),
            modeled_risk=Decimal(shares) * (stop_distance or Decimal("0")),
            cash_reserve=reserve,
            sector_weight_before_pct=before,
            sector_weight_after_pct=self._pct(before * equity / self.PCT + allocation, equity),
            normalized_sizing_weight=normalized_weight,
        )

    @staticmethod
    def _pct(value: Decimal, equity: Decimal) -> Decimal:
        return value / equity * Decimal("100") if equity > 0 else Decimal("0")
