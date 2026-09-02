from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DailyBriefDataStatusSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    readiness: str
    expected_completed_session: date | None
    latest_synchronized_session: date | None
    brief_session: date | None
    sync_status: str
    explanation: str


class DailyBriefSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portfolio_value: Decimal | None
    cash: Decimal
    invested_market_value: Decimal | None
    cash_pct: Decimal | None
    open_positions: int
    max_positions: int
    valuation_readiness: str
    modeled_risk_dollars: Decimal | None


class DailyBriefReferenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reference_type: str
    value: Decimal
    condition: str
    qualifier: str
    distance_dollars: Decimal | None
    distance_pct: Decimal | None


class DailyBriefPositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    position_id: UUID
    ticker: str
    company_name: str | None
    strategy: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    status: str
    reason: str
    explanation: str
    quantity: int
    latest_completed_close: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    as_of_session: date | None
    sticky_sell: bool
    exit_triggered_on: date | None
    loss_control_policy: str
    loss_control_boundary: Decimal | None
    loss_control_trigger: str | None
    broker_stop_order: bool
    references: list[DailyBriefReferenceSchema]
    base_status: str | None = None
    news_effect: str = "NO_EFFECT"
    news_coverage: str = "NEVER_REFRESHED"
    final_status: str | None = None
    news_reason: str | None = None
    news_policy_version: str | None = None
    supporting_news_article_ids: list[UUID] = []
    aggregate_sentiment_score: Decimal | None = None
    aggregate_bullish_pct: Decimal | None = None
    aggregate_bearish_pct: Decimal | None = None
    aggregate_mentions: int | None = None
    aggregate_source_count: int | None = None
    aggregate_buzz_score: Decimal | None = None
    aggregate_trend: str | None = None
    aggregate_observed_at: datetime | None = None
    aggregate_evidence_strength: str = "UNAVAILABLE"
    aggregate_effect: str = "UNAVAILABLE"
    aggregate_limitation: str | None = None


class DailyBriefOpportunitySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    strategy: str
    strategy_profile_id: str
    strategy_profile_version: int
    source_plan_id: str
    portfolio_revision: int
    selection_policy: str
    sizing_policy: str
    decision: str
    decision_reason: str
    ranking_score: Decimal | None
    reference_price: Decimal
    proposed_shares: int
    target_allocation_dollars: Decimal
    target_weight_pct: Decimal
    sector: str
    execution_readiness: str
    execution_readiness_reason: str
    loss_control_policy: str
    loss_control_boundary: Decimal | None
    loss_control_trigger: str | None
    loss_control_distance_dollars: Decimal | None
    loss_control_distance_pct: Decimal | None
    broker_stop_order: bool
    strategy_references: list[DailyBriefReferenceSchema]
    analysis_as_of_date: date
    action_id: str | None
    workflow_status: str
    base_decision: str | None = None
    news_coverage: str = "NEVER_REFRESHED"
    news_effect: str = "NO_EFFECT"
    final_decision: str | None = None
    news_reason: str | None = None
    news_policy_version: str | None = None
    supporting_news_article_ids: list[UUID] = []


class DailyPortfolioBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portfolio_id: UUID
    portfolio_revision: int
    generated_at: datetime
    data_status: DailyBriefDataStatusSchema
    workflow_status: str
    summary: DailyBriefSummarySchema
    required_actions: list[DailyBriefPositionSchema]
    attention_positions: list[DailyBriefPositionSchema]
    actionable_opportunities: list[DailyBriefOpportunitySchema]
    research_only_opportunities: list[DailyBriefOpportunitySchema]
    deferred_opportunities: list[DailyBriefOpportunitySchema]
    hold_positions: list[DailyBriefPositionSchema]
    unavailable_positions: list[DailyBriefPositionSchema]
    blockers: list[str]


class DailyPortfolioBriefCoreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portfolio_id: UUID
    portfolio_revision: int
    generated_at: datetime
    data_status: DailyBriefDataStatusSchema
    workflow_status: str
    summary: DailyBriefSummarySchema
    required_actions: list[DailyBriefPositionSchema]
    attention_positions: list[DailyBriefPositionSchema]
    hold_positions: list[DailyBriefPositionSchema]
    unavailable_positions: list[DailyBriefPositionSchema]
    blockers: list[str]


class DailyBriefOpportunitiesSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portfolio_id: UUID
    portfolio_revision: int
    generated_at: datetime
    analysis_as_of_date: date | None
    workflow_status: str
    actionable_opportunities: list[DailyBriefOpportunitySchema]
    research_only_opportunities: list[DailyBriefOpportunitySchema]
    deferred_opportunities: list[DailyBriefOpportunitySchema]
    actionable_total_count: int
    research_only_total_count: int
    deferred_total_count: int
    research_only_limit: int | None
