from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.portfolio.actions import (
    ManualSellPriceSource,
    ManualSellReason,
    PlanActionApplyReason,
    PlanActionQuantitySemantics,
    PlanActionValidationStatus,
)
from alphapilot.portfolio.exit_guidance import FixedTakeProfitPolicy, StrategyExitState
from alphapilot.portfolio.orchestration import CandidateDataStatus, PlanReadinessStatus
from alphapilot.portfolio.sizing import (
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingPolicyName,
)
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


class PortfolioRiskConfigSchema(BaseModel):
    risk_per_position_pct: Decimal = Field(default=Decimal("1"), gt=0)
    atr_period: int = Field(default=14, gt=0)
    atr_stop_multiple: Decimal = Field(default=Decimal("2"), gt=0)
    max_position_weight_pct: Decimal = Field(default=Decimal("10"), gt=0)
    max_portfolio_risk_pct: Decimal = Field(default=Decimal("8"), gt=0)
    minimum_cash_reserve_pct: Decimal = Field(default=Decimal("10"), ge=0, lt=100)
    max_sector_weight_pct: Decimal = Field(default=Decimal("30"), gt=0)
    max_positions: int = Field(default=10, gt=0)


class PortfolioPositionSchema(BaseModel):
    ticker: str
    shares: int = Field(gt=0)
    reference_price: Decimal = Field(gt=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)
    sector: str | None = None
    modeled_risk_dollars: Decimal = Field(default=Decimal("0"), ge=0)


class CurrentPortfolioSchema(BaseModel):
    cash: Decimal = Field(ge=0)
    positions: list[PortfolioPositionSchema] = []


class PortfolioCandidateSchema(BaseModel):
    ticker: str
    signal: Signal
    reference_price: Decimal = Field(gt=0)
    ranking_score: Decimal | None = None
    atr: Decimal | None = Field(default=None, ge=0)
    sector: str | None = None


class PortfolioDecisionRequest(BaseModel):
    strategy: str
    strategy_parameters: dict[str, str | Decimal] = {}
    selection_policy: str = "relative-strength-20"
    sizing_policy: SizingPolicyName = SizingPolicyName.ATR_RISK
    portfolio: CurrentPortfolioSchema
    risk_config: PortfolioRiskConfigSchema = PortfolioRiskConfigSchema()
    candidates: list[PortfolioCandidateSchema]


class StrategyExitContextSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    strategy: StrategyName
    data_as_of_date: date
    reference_close: Decimal
    current_signal: Signal
    signal_reason: str
    exit_mode: str
    current_exit_state: StrategyExitState
    fixed_take_profit_policy: FixedTakeProfitPolicy
    ema20: Decimal | None = None
    ema50: Decimal | None = None
    ema_spread_pct: Decimal | None = None
    hybrid_threshold_pct: Decimal | None = None
    distance_to_ema20_pct: Decimal | None = None
    distance_to_ema50_pct: Decimal | None = None
    sma150: Decimal | None = None
    distance_to_sma150_pct: Decimal | None = None


class PortfolioDecisionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
    depends_on_action_ids: list[str] = []
    exit_context: StrategyExitContextSchema | None = None


class PortfolioPositionSummarySchema(BaseModel):
    ticker: str
    shares: int
    reference_price: Decimal
    market_value: Decimal
    portfolio_weight_pct: Decimal
    cost_basis: Decimal | None
    sector: str
    modeled_risk_dollars: Decimal


class PortfolioSummarySchema(BaseModel):
    equity: Decimal
    cash: Decimal
    cash_pct: Decimal
    invested_value: Decimal
    invested_pct: Decimal
    cash_reserve_requirement: Decimal
    current_portfolio_risk: Decimal
    current_portfolio_risk_pct: Decimal
    available_portfolio_risk: Decimal
    available_portfolio_risk_pct: Decimal
    modeled_risk_complete: bool
    open_positions: int
    positions: list[PortfolioPositionSummarySchema]


class PortfolioDraftSummarySchema(BaseModel):
    equity: Decimal
    cash: Decimal
    cash_pct: Decimal
    invested_value: Decimal
    invested_pct: Decimal
    open_positions: int
    positions: list[PortfolioPositionSummarySchema]


class PortfolioDecisionPlanSchema(BaseModel):
    portfolio: PortfolioSummarySchema
    config: PortfolioRiskConfigSchema
    strategy: str
    selection_policy: str
    sizing_policy: SizingPolicyName = SizingPolicyName.ATR_RISK
    decisions: list[PortfolioDecisionSchema]


class PortfolioPlanRequest(BaseModel):
    strategy: StrategyName
    exit_mode: TrendExitMode = TrendExitMode.HYBRID
    hybrid_trend_threshold_pct: Decimal = Decimal("2")
    micho_entry_mode: MichoEntryMode = MichoEntryMode.BOTH
    selection_policy: SelectionPolicyName = SelectionPolicyName.RELATIVE_STRENGTH_20
    sizing_policy: SizingPolicyName = SizingPolicyName.ATR_VOLATILITY_NORMALIZED
    as_of_date: date = Field(default_factory=date.today)
    tickers: list[str] | None = None
    portfolio: CurrentPortfolioSchema
    risk_config: PortfolioRiskConfigSchema = PortfolioRiskConfigSchema()

    @model_validator(mode="after")
    def enforce_frozen_strategy_parameters(self) -> "PortfolioPlanRequest":
        if self.strategy == StrategyName.EMA20_PULLBACK and (
            self.exit_mode != TrendExitMode.HYBRID
            or self.hybrid_trend_threshold_pct != Decimal("2")
        ):
            raise ValueError("Sprint 10B EMA plans require HYBRID with threshold 2%")
        if self.strategy == StrategyName.MICHO_150 and (
            self.micho_entry_mode != MichoEntryMode.BOTH
        ):
            raise ValueError("Sprint 10B Micho plans require BOTH entry mode")
        return self


class CandidateOrchestrationStatusSchema(BaseModel):
    ticker: str
    status: CandidateDataStatus
    data_as_of_date: date | None
    signal: Signal | None
    reason: str
    company_name: str | None = None
    sector: str | None = None
    ranking_score: Decimal | None = None
    atr: Decimal | None = None
    decision: PortfolioDecisionType | None = None
    decision_reason: PortfolioDecisionReason | None = None
    candidate_rank: int | None = None
    is_custom_tracked: bool = False
    company_id: UUID | None = None


class PortfolioPlanReadinessSchema(BaseModel):
    status: PlanReadinessStatus
    requested_tickers: int
    evaluated_tickers: int
    fresh_tickers: int
    stale_tickers: int
    no_data_tickers: int
    insufficient_history_tickers: int
    company_not_found_tickers: int
    buy_signals: int
    approved_buys: int
    approved_sells: int
    actionable_decisions: int
    latest_ticker_data_date: date | None
    buy_rejections_by_reason: dict[str, int]


class PortfolioPlanSchema(PortfolioDecisionPlanSchema):
    plan_id: str
    requested_as_of_date: date
    analysis_as_of_date: date
    candidate_statuses: list[CandidateOrchestrationStatusSchema]
    readiness: PortfolioPlanReadinessSchema
    evaluation_target_ticker: str | None = None


class PortfolioPlanActionRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    portfolio: CurrentPortfolioSchema
    decision: PortfolioDecisionSchema
    applied_action_ids: list[str] = []
    requested_shares: int | None = Field(default=None, gt=0)
    sizing_policy: SizingPolicyName = SizingPolicyName.ATR_RISK
    risk_config: PortfolioRiskConfigSchema = PortfolioRiskConfigSchema()


class PortfolioPlanActionResultSchema(BaseModel):
    plan_id: str
    applied: bool
    reason: PlanActionApplyReason
    action_id: str | None
    action_type: PortfolioDecisionType
    cash_before: Decimal
    cash_impact: Decimal
    cash_after: Decimal
    position_before: PortfolioPositionSchema | None
    position_after: PortfolioPositionSchema | None
    portfolio: CurrentPortfolioSchema
    summary: PortfolioDraftSummarySchema
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


class LatestStoredPriceSchema(BaseModel):
    ticker: str
    price: Decimal | None
    price_date: date | None
    source: str = "LATEST_STORED_CANDLE"


class ManualSellRequestSchema(BaseModel):
    portfolio: CurrentPortfolioSchema
    ticker: str = Field(min_length=1, max_length=10)
    shares_to_sell: int = Field(gt=0)
    execution_price: Decimal | None = Field(default=None, gt=0)


class ManualSellResultSchema(BaseModel):
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
    portfolio: CurrentPortfolioSchema
    summary: PortfolioDraftSummarySchema
