from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
from alphapilot.strategy.profile import (
    ResearchClassification,
    TradeManagementDefault,
)
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


class StrategyProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    profile_id: str
    version: int
    strategy: StrategyName
    display_name: str
    classification: ResearchClassification
    entry_description: str
    recommended_selection_policy: SelectionPolicyName
    allowed_selection_policies: list[SelectionPolicyName]
    sizing_policy: SizingPolicyName
    strategy_exit_description: str
    ema_exit_mode: TrendExitMode | None
    hybrid_trend_threshold_pct: Decimal | None
    micho_entry_mode: MichoEntryMode | None
    protective_stop_default: TradeManagementDefault
    profit_management_default: TradeManagementDefault
    research_only_stop_candidate: str


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
    model_config = ConfigDict(extra="forbid")
    strategy: StrategyName
    selection_policy: SelectionPolicyName = SelectionPolicyName.RELATIVE_STRENGTH_20
    as_of_date: date = Field(default_factory=date.today)
    tickers: list[str] | None = None
    portfolio_id: UUID | None = None
    portfolio: CurrentPortfolioSchema | None = None
    risk_config: PortfolioRiskConfigSchema = PortfolioRiskConfigSchema()


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
    strategy_profile: StrategyProfileSchema
    requested_as_of_date: date
    analysis_as_of_date: date
    candidate_statuses: list[CandidateOrchestrationStatusSchema]
    readiness: PortfolioPlanReadinessSchema
    evaluation_target_ticker: str | None = None
    portfolio_id: UUID | None = None
    portfolio_revision: int | None = None


class PortfolioPlanActionRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    portfolio_id: UUID | None = None
    portfolio_revision: int | None = Field(default=None, ge=0)
    analysis_as_of_date: date | None = None
    selection_policy: SelectionPolicyName = SelectionPolicyName.RELATIVE_STRENGTH_20
    portfolio: CurrentPortfolioSchema | None = None
    decision: PortfolioDecisionSchema
    applied_action_ids: list[str] = []
    requested_shares: int | None = Field(default=None, gt=0)
    strategy_profile_id: str = Field(min_length=1)
    strategy_profile_version: int = Field(gt=0)
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
    portfolio_id: UUID | None = None
    portfolio_revision: int | None = None


class LatestStoredPriceSchema(BaseModel):
    ticker: str
    price: Decimal | None
    price_date: date | None
    source: str = "LATEST_STORED_CANDLE"


class ManualSellRequestSchema(BaseModel):
    portfolio_id: UUID | None = None
    portfolio_revision: int | None = Field(default=None, ge=0)
    portfolio: CurrentPortfolioSchema | None = None
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
    portfolio_id: UUID | None = None
    portfolio_revision: int | None = None


class ImportedResearchPositionSchema(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    quantity: int = Field(gt=0)
    average_cost: Decimal = Field(gt=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)


class ResearchPortfolioInitializeSchema(BaseModel):
    starting_cash: Decimal = Field(ge=0)
    name: str = Field(default="AlphaPilot Research Portfolio", min_length=1, max_length=150)
    imported_positions: list[ImportedResearchPositionSchema] = []


class ResearchPositionValuationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    position_id: UUID
    company_id: UUID
    ticker: str
    sector: str | None
    status: str
    quantity: int
    average_cost: Decimal
    cost_basis: Decimal
    entry_trading_day: date | None
    entry_price: Decimal | None
    strategy: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    selection_policy: str | None
    provenance_status: str
    modeled_risk_dollars: Decimal
    latest_completed_trading_day: date | None
    latest_completed_close: Decimal | None
    market_value: Decimal | None
    portfolio_weight_pct: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    valuation_status: str


class ResearchPortfolioSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portfolio_id: UUID
    stable_key: str
    name: str
    revision: int
    cash: Decimal
    realized_pnl: Decimal
    total_cost_basis: Decimal
    positions_market_value: Decimal | None
    total_equity: Decimal | None
    cash_pct: Decimal | None
    invested_pct: Decimal | None
    total_unrealized_pnl: Decimal | None
    latest_completed_trading_day: date | None
    valuation_status: str
    positions: list[ResearchPositionValuationSchema]


class ResearchTradeEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    quantity: int
    execution_price: Decimal
    trading_day: date | None
    cash_effect: Decimal
    realized_pnl: Decimal
    source: str
    reason: str | None
    action_id: str | None
    strategy: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    provenance_status: str


class ResearchReconciliationEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    position_id: UUID | None
    event_type: str
    portfolio_revision: int
    cash_delta: Decimal | None
    before_facts: dict[str, object] | None
    after_facts: dict[str, object] | None
    reason: str


class PositionMonitoringSchema(BaseModel):
    position_id: UUID
    ticker: str
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    readiness: str
    status: str | None
    reason: str
    completed_trading_day: date | None
    latest_close: Decimal | None
    indicator_facts: dict[str, str | bool | None]
    exit_triggered: bool
    exit_triggered_on: date | None
    exit_trigger_reason: str | None
    protective_stop_policy: str
    trailing_stop_policy: str
    profit_target_policy: str


class CashAdjustmentRequestSchema(BaseModel):
    expected_revision: int = Field(ge=0)
    delta: Decimal
    reason: str = Field(min_length=1, max_length=200)


class ExternalPositionRequestSchema(BaseModel):
    expected_revision: int = Field(ge=0)
    ticker: str = Field(min_length=1, max_length=10)
    quantity: int = Field(gt=0)
    average_cost: Decimal = Field(gt=0)
    entry_trading_day: date | None = None
    reason: str = Field(min_length=1, max_length=200)


class PositionReconciliationRequestSchema(BaseModel):
    expected_revision: int = Field(ge=0)
    quantity: int = Field(gt=0)
    average_cost: Decimal = Field(gt=0)
    entry_trading_day: date | None = None
    reason: str = Field(min_length=1, max_length=200)
