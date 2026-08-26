from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from alphapilot.portfolio.exit_guidance import StrategyExitContext
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import (
    AtrRiskPositionSizer,
    AtrVolatilityNormalizedPositionSizer,
    EqualSlotPositionSizer,
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingContext,
    SizingDecision,
    SizingPolicyName,
    VolatilityBatchContext,
    VolatilitySizingCandidate,
)
from alphapilot.strategy.signal import Signal

UNCLASSIFIED_SECTOR = "Unclassified"


@dataclass(slots=True, frozen=True)
class PortfolioStatePosition:
    ticker: str
    shares: int
    reference_price: Decimal
    cost_basis: Decimal | None = None
    sector: str | None = None
    modeled_risk_dollars: Decimal = Decimal("0")

    @property
    def market_value(self) -> Decimal:
        return Decimal(self.shares) * self.reference_price


@dataclass(slots=True, frozen=True)
class CurrentPortfolioState:
    cash: Decimal
    positions: tuple[PortfolioStatePosition, ...] = ()

    @property
    def equity(self) -> Decimal:
        return self.cash + sum((item.market_value for item in self.positions), Decimal("0"))


@dataclass(slots=True, frozen=True)
class PortfolioCandidate:
    ticker: str
    signal: Signal
    reference_price: Decimal
    ranking_score: Decimal | None = None
    atr: Decimal | None = None
    sector: str | None = None
    pre_decision_reason: PortfolioDecisionReason | None = None
    exit_context: StrategyExitContext | None = None


@dataclass(slots=True, frozen=True)
class PortfolioDecision:
    ticker: str
    signal: Signal
    decision: PortfolioDecisionType
    reason: PortfolioDecisionReason
    ranking_score: Decimal | None
    reference_price: Decimal
    atr: Decimal | None
    stop_distance: Decimal | None
    risk_budget_dollars: Decimal
    target_allocation_dollars: Decimal
    target_weight_pct: Decimal
    proposed_shares: int
    modeled_position_risk_dollars: Decimal
    sector: str
    sector_weight_before_pct: Decimal
    sector_weight_after_pct: Decimal
    current_shares: int
    estimated_proceeds: Decimal | None
    normalized_sizing_weight: Decimal | None = None
    estimated_cash_outlay: Decimal | None = None
    cash_after_decision: Decimal | None = None
    modeled_stop_reference_price: Decimal | None = None
    action_id: str | None = None
    application_order: int | None = None
    depends_on_action_ids: tuple[str, ...] = ()
    exit_context: StrategyExitContext | None = None


@dataclass(slots=True, frozen=True)
class PortfolioDecisionPlan:
    equity: Decimal
    cash: Decimal
    cash_reserve_requirement: Decimal
    current_portfolio_risk: Decimal
    available_portfolio_risk: Decimal
    open_positions: int
    decisions: tuple[PortfolioDecision, ...]


class PortfolioDecisionEngine:
    def __init__(self, sizer: AtrRiskPositionSizer | None = None) -> None:
        self.sizer = sizer or AtrRiskPositionSizer()

    def build_plan(
        self,
        state: CurrentPortfolioState,
        candidates: tuple[PortfolioCandidate, ...],
        config: PortfolioRiskConfig | None = None,
        sizing_policy: SizingPolicyName = SizingPolicyName.ATR_RISK,
    ) -> PortfolioDecisionPlan:
        risk_config = config or PortfolioRiskConfig()
        if sizing_policy == SizingPolicyName.ATR_VOLATILITY_NORMALIZED:
            return self._build_volatility_plan(state, candidates, risk_config)
        equity = state.equity
        cash = state.cash
        positions = {item.ticker.upper(): item for item in state.positions}
        current_risk = sum((item.modeled_risk_dollars for item in positions.values()), Decimal("0"))
        sector_values: dict[str, Decimal] = {}
        for item in positions.values():
            sector = self._sector(item.sector)
            sector_values[sector] = sector_values.get(sector, Decimal("0")) + item.market_value
        decisions: list[PortfolioDecision] = []

        ordered = sorted(
            candidates,
            key=lambda item: (
                item.signal != Signal.SELL,
                item.signal != Signal.BUY,
                item.ranking_score is None,
                -(item.ranking_score or Decimal("0")),
                item.ticker.upper(),
            ),
        )
        for candidate in ordered:
            ticker = candidate.ticker.upper()
            held = positions.get(ticker)
            sector = self._sector(candidate.sector)
            if candidate.pre_decision_reason is not None:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.SKIP,
                        candidate.pre_decision_reason,
                        sector,
                        held,
                    )
                )
                continue
            if candidate.signal == Signal.SELL:
                decisions.append(self._sell(candidate, held, sector))
                if held is not None:
                    cash += held.market_value
                    current_risk -= held.modeled_risk_dollars
                    sector_values[sector] = max(
                        sector_values.get(sector, Decimal("0")) - held.market_value,
                        Decimal("0"),
                    )
                    del positions[ticker]
                continue
            if candidate.signal != Signal.BUY:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.HOLD,
                        PortfolioDecisionReason.NO_ACTION,
                        sector,
                        held,
                    )
                )
                continue
            if held is not None:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.SKIP,
                        PortfolioDecisionReason.ALREADY_HELD,
                        sector,
                        held,
                    )
                )
                continue
            if len(positions) >= risk_config.max_positions:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.SKIP,
                        PortfolioDecisionReason.MAX_POSITIONS,
                        sector,
                        None,
                    )
                )
                continue
            sizing_context = SizingContext(
                equity=equity,
                cash=cash,
                execution_price=candidate.reference_price,
                atr=candidate.atr,
                current_portfolio_risk=current_risk,
                sector_market_value=sector_values.get(sector, Decimal("0")),
            )
            sizing = (
                EqualSlotPositionSizer().size(sizing_context, risk_config)
                if sizing_policy == SizingPolicyName.EQUAL_SLOT
                else self.sizer.size(sizing_context, risk_config)
            )
            approved = sizing.shares > 0
            decisions.append(
                PortfolioDecision(
                    ticker=ticker,
                    signal=candidate.signal,
                    decision=(
                        PortfolioDecisionType.BUY if approved else PortfolioDecisionType.SKIP
                    ),
                    reason=sizing.reason,
                    ranking_score=candidate.ranking_score,
                    reference_price=candidate.reference_price,
                    atr=sizing.atr,
                    stop_distance=sizing.stop_distance,
                    risk_budget_dollars=sizing.risk_budget,
                    target_allocation_dollars=sizing.allocation,
                    target_weight_pct=sizing.position_weight_pct,
                    proposed_shares=sizing.shares,
                    modeled_position_risk_dollars=sizing.modeled_risk,
                    sector=sector,
                    sector_weight_before_pct=sizing.sector_weight_before_pct,
                    sector_weight_after_pct=sizing.sector_weight_after_pct,
                    current_shares=0,
                    estimated_proceeds=None,
                    normalized_sizing_weight=sizing.normalized_sizing_weight,
                    exit_context=candidate.exit_context,
                )
            )
            if approved:
                new_position = PortfolioStatePosition(
                    ticker=ticker,
                    shares=sizing.shares,
                    reference_price=candidate.reference_price,
                    sector=sector,
                    modeled_risk_dollars=sizing.modeled_risk,
                )
                positions[ticker] = new_position
                cash -= sizing.allocation
                current_risk += sizing.modeled_risk
                sector_values[sector] = sector_values.get(sector, Decimal("0")) + sizing.allocation

        risk_limit = equity * risk_config.max_portfolio_risk_pct / Decimal("100")
        return PortfolioDecisionPlan(
            equity=equity,
            cash=state.cash,
            cash_reserve_requirement=(
                equity * risk_config.minimum_cash_reserve_pct / Decimal("100")
            ),
            current_portfolio_risk=sum(
                (item.modeled_risk_dollars for item in state.positions), Decimal("0")
            ),
            available_portfolio_risk=max(
                risk_limit
                - sum((item.modeled_risk_dollars for item in state.positions), Decimal("0")),
                Decimal("0"),
            ),
            open_positions=len(state.positions),
            decisions=self._workflow_decisions(state, tuple(decisions)),
        )

    def _build_volatility_plan(
        self,
        state: CurrentPortfolioState,
        candidates: tuple[PortfolioCandidate, ...],
        config: PortfolioRiskConfig,
    ) -> PortfolioDecisionPlan:
        equity = state.equity
        cash = state.cash
        positions = {item.ticker.upper(): item for item in state.positions}
        current_risk = sum((item.modeled_risk_dollars for item in positions.values()), Decimal("0"))
        sector_values: dict[str, Decimal] = {}
        for item in positions.values():
            sector = self._sector(item.sector)
            sector_values[sector] = sector_values.get(sector, Decimal("0")) + item.market_value
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.signal != Signal.SELL,
                item.signal != Signal.BUY,
                item.ranking_score is None,
                -(item.ranking_score or Decimal("0")),
                item.ticker.upper(),
            ),
        )
        decisions: list[PortfolioDecision] = []
        buy_candidates: list[PortfolioCandidate] = []

        for candidate in ordered:
            ticker = candidate.ticker.upper()
            held = positions.get(ticker)
            sector = self._sector(candidate.sector)
            if candidate.pre_decision_reason is not None:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.SKIP,
                        candidate.pre_decision_reason,
                        sector,
                        held,
                    )
                )
            elif candidate.signal == Signal.SELL:
                decisions.append(self._sell(candidate, held, sector))
                if held is not None:
                    cash += held.market_value
                    current_risk -= held.modeled_risk_dollars
                    held_sector = self._sector(held.sector)
                    sector_values[held_sector] = max(
                        sector_values.get(held_sector, Decimal("0")) - held.market_value,
                        Decimal("0"),
                    )
                    del positions[ticker]
            elif candidate.signal != Signal.BUY:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.HOLD,
                        PortfolioDecisionReason.NO_ACTION,
                        sector,
                        held,
                    )
                )
            elif held is not None:
                decisions.append(
                    self._simple(
                        candidate,
                        PortfolioDecisionType.SKIP,
                        PortfolioDecisionReason.ALREADY_HELD,
                        sector,
                        held,
                    )
                )
            else:
                buy_candidates.append(candidate)

        allocations = AtrVolatilityNormalizedPositionSizer().allocate(
            VolatilityBatchContext(
                equity=equity,
                cash=cash,
                invested_value=sum(
                    (position.market_value for position in positions.values()), Decimal("0")
                ),
                current_portfolio_risk=current_risk,
                sector_market_values=sector_values,
                available_slots=max(config.max_positions - len(positions), 0),
            ),
            [
                VolatilitySizingCandidate(
                    ticker=candidate.ticker.upper(),
                    execution_price=candidate.reference_price,
                    atr=candidate.atr,
                    sector=self._sector(candidate.sector),
                )
                for candidate in buy_candidates
            ],
            config,
        )
        allocation_by_ticker = {item.ticker: item.decision for item in allocations}
        for candidate in buy_candidates:
            ticker = candidate.ticker.upper()
            sector = self._sector(candidate.sector)
            sizing = allocation_by_ticker[ticker]
            decisions.append(self._from_sizing(candidate, sector, sizing))
            if sizing.shares > 0:
                positions[ticker] = PortfolioStatePosition(
                    ticker=ticker,
                    shares=sizing.shares,
                    reference_price=candidate.reference_price,
                    sector=sector,
                    modeled_risk_dollars=sizing.modeled_risk,
                )
                cash -= sizing.allocation
                current_risk += sizing.modeled_risk
                sector_values[sector] = sector_values.get(sector, Decimal("0")) + sizing.allocation

        return self._plan_summary(state, config, tuple(decisions))

    @staticmethod
    def _from_sizing(
        candidate: PortfolioCandidate,
        sector: str,
        sizing: SizingDecision,
    ) -> PortfolioDecision:
        approved = sizing.shares > 0
        return PortfolioDecision(
            ticker=candidate.ticker.upper(),
            signal=candidate.signal,
            decision=PortfolioDecisionType.BUY if approved else PortfolioDecisionType.SKIP,
            reason=sizing.reason,
            ranking_score=candidate.ranking_score,
            reference_price=candidate.reference_price,
            atr=sizing.atr,
            stop_distance=sizing.stop_distance,
            risk_budget_dollars=sizing.risk_budget,
            target_allocation_dollars=sizing.allocation,
            target_weight_pct=sizing.position_weight_pct,
            proposed_shares=sizing.shares,
            modeled_position_risk_dollars=sizing.modeled_risk,
            sector=sector,
            sector_weight_before_pct=sizing.sector_weight_before_pct,
            sector_weight_after_pct=sizing.sector_weight_after_pct,
            current_shares=0,
            estimated_proceeds=None,
            normalized_sizing_weight=sizing.normalized_sizing_weight,
            exit_context=candidate.exit_context,
        )

    @staticmethod
    def _plan_summary(
        state: CurrentPortfolioState,
        config: PortfolioRiskConfig,
        decisions: tuple[PortfolioDecision, ...],
    ) -> PortfolioDecisionPlan:
        equity = state.equity
        current_risk = sum((item.modeled_risk_dollars for item in state.positions), Decimal("0"))
        risk_limit = equity * config.max_portfolio_risk_pct / Decimal("100")
        return PortfolioDecisionPlan(
            equity=equity,
            cash=state.cash,
            cash_reserve_requirement=(equity * config.minimum_cash_reserve_pct / Decimal("100")),
            current_portfolio_risk=current_risk,
            available_portfolio_risk=max(risk_limit - current_risk, Decimal("0")),
            open_positions=len(state.positions),
            decisions=PortfolioDecisionEngine._workflow_decisions(state, decisions),
        )

    @staticmethod
    def _workflow_decisions(
        state: CurrentPortfolioState,
        decisions: tuple[PortfolioDecision, ...],
    ) -> tuple[PortfolioDecision, ...]:
        """Add exact research-draft action values without synthetic rank dependencies."""
        enriched: list[PortfolioDecision] = []
        cash = state.cash
        action_order = 0
        for decision in decisions:
            outlay: Decimal | None = None
            cash_after: Decimal | None = None
            stop_reference: Decimal | None = None
            if decision.decision == PortfolioDecisionType.BUY and decision.proposed_shares > 0:
                action_order += 1
                outlay = decision.target_allocation_dollars
                candidate_cash = cash - outlay
                cash_after = candidate_cash if candidate_cash >= 0 else None
                if cash_after is not None:
                    cash = cash_after
                if decision.stop_distance is not None:
                    candidate_stop = decision.reference_price - decision.stop_distance
                    stop_reference = candidate_stop if candidate_stop > 0 else None
            elif (
                decision.decision == PortfolioDecisionType.SELL
                and decision.estimated_proceeds is not None
            ):
                action_order += 1
                cash += decision.estimated_proceeds
                cash_after = cash
            action_id = (
                f"{action_order}:{decision.decision.value}:{decision.ticker}"
                if action_order > 0 and (outlay is not None or cash_after is not None)
                else None
            )
            enriched.append(
                replace(
                    decision,
                    estimated_cash_outlay=outlay,
                    cash_after_decision=cash_after,
                    modeled_stop_reference_price=stop_reference,
                    action_id=action_id,
                    application_order=action_order if action_id is not None else None,
                    depends_on_action_ids=(),
                )
            )
        return tuple(enriched)

    @staticmethod
    def _sector(value: str | None) -> str:
        return value.strip() if value and value.strip() else UNCLASSIFIED_SECTOR

    def _sell(
        self, candidate: PortfolioCandidate, held: PortfolioStatePosition | None, sector: str
    ) -> PortfolioDecision:
        if held is None:
            return self._simple(
                candidate,
                PortfolioDecisionType.SKIP,
                PortfolioDecisionReason.NO_POSITION_TO_SELL,
                sector,
                None,
            )
        result = self._simple(
            candidate,
            PortfolioDecisionType.SELL,
            PortfolioDecisionReason.SELL_APPROVED,
            sector,
            held,
        )
        return replace(result, estimated_proceeds=held.market_value)

    @staticmethod
    def _simple(
        candidate: PortfolioCandidate,
        decision: PortfolioDecisionType,
        reason: PortfolioDecisionReason,
        sector: str,
        held: PortfolioStatePosition | None,
    ) -> PortfolioDecision:
        return PortfolioDecision(
            ticker=candidate.ticker.upper(),
            signal=candidate.signal,
            decision=decision,
            reason=reason,
            ranking_score=candidate.ranking_score,
            reference_price=candidate.reference_price,
            atr=candidate.atr,
            stop_distance=None,
            risk_budget_dollars=Decimal("0"),
            target_allocation_dollars=Decimal("0"),
            target_weight_pct=Decimal("0"),
            proposed_shares=0,
            modeled_position_risk_dollars=Decimal("0"),
            sector=sector,
            sector_weight_before_pct=Decimal("0"),
            sector_weight_after_pct=Decimal("0"),
            current_shares=(held.shares if held else 0),
            estimated_proceeds=None,
            normalized_sizing_weight=None,
            exit_context=candidate.exit_context,
        )
