from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.portfolio.orchestration import CandidateDataStatus
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


class PortfolioSummarySchema(BaseModel):
    equity: Decimal
    cash: Decimal
    cash_reserve_requirement: Decimal
    current_portfolio_risk: Decimal
    available_portfolio_risk: Decimal
    open_positions: int


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


class PortfolioPlanSchema(PortfolioDecisionPlanSchema):
    requested_as_of_date: date
    analysis_as_of_date: date
    candidate_statuses: list[CandidateOrchestrationStatusSchema]
