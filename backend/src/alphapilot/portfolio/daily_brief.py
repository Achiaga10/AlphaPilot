from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class DailyBriefReadiness(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class DailyBriefWorkflowStatus(StrEnum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    WAITING_FOR_REQUIRED_EXITS = "WAITING_FOR_REQUIRED_EXITS"
    NEW_ENTRIES_BLOCKED = "NEW_ENTRIES_BLOCKED"


@dataclass(frozen=True, slots=True)
class DailyBriefDataStatus:
    readiness: DailyBriefReadiness
    expected_completed_session: date | None
    latest_synchronized_session: date | None
    brief_session: date | None
    sync_status: str
    explanation: str


@dataclass(frozen=True, slots=True)
class DailyBriefSummary:
    portfolio_value: Decimal | None
    cash: Decimal
    invested_market_value: Decimal | None
    cash_pct: Decimal | None
    open_positions: int
    max_positions: int
    valuation_readiness: str
    modeled_risk_dollars: Decimal | None


@dataclass(frozen=True, slots=True)
class DailyBriefReference:
    reference_type: str
    value: Decimal
    condition: str
    qualifier: str
    distance_dollars: Decimal | None
    distance_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class DailyBriefPosition:
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
    references: tuple[DailyBriefReference, ...]
    base_status: str | None = None
    news_effect: str = "NO_EFFECT"
    news_coverage: str = "NEVER_REFRESHED"
    final_status: str | None = None
    news_reason: str | None = None
    news_policy_version: str | None = None
    supporting_news_article_ids: tuple[UUID, ...] = ()
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


@dataclass(frozen=True, slots=True)
class DailyBriefOpportunity:
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
    strategy_references: tuple[DailyBriefReference, ...]
    analysis_as_of_date: date
    action_id: str | None
    workflow_status: str
    base_decision: str | None = None
    news_coverage: str = "NEVER_REFRESHED"
    news_effect: str = "NO_EFFECT"
    final_decision: str | None = None
    news_reason: str | None = None
    news_policy_version: str | None = None
    supporting_news_article_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class DailyPortfolioBrief:
    portfolio_id: UUID
    portfolio_revision: int
    generated_at: datetime
    data_status: DailyBriefDataStatus
    workflow_status: DailyBriefWorkflowStatus
    summary: DailyBriefSummary
    required_actions: tuple[DailyBriefPosition, ...]
    attention_positions: tuple[DailyBriefPosition, ...]
    actionable_opportunities: tuple[DailyBriefOpportunity, ...]
    research_only_opportunities: tuple[DailyBriefOpportunity, ...]
    deferred_opportunities: tuple[DailyBriefOpportunity, ...]
    hold_positions: tuple[DailyBriefPosition, ...]
    unavailable_positions: tuple[DailyBriefPosition, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DailyPortfolioBriefCore:
    portfolio_id: UUID
    portfolio_revision: int
    generated_at: datetime
    data_status: DailyBriefDataStatus
    workflow_status: DailyBriefWorkflowStatus
    summary: DailyBriefSummary
    required_actions: tuple[DailyBriefPosition, ...]
    attention_positions: tuple[DailyBriefPosition, ...]
    hold_positions: tuple[DailyBriefPosition, ...]
    unavailable_positions: tuple[DailyBriefPosition, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DailyBriefOpportunities:
    portfolio_id: UUID
    portfolio_revision: int
    generated_at: datetime
    analysis_as_of_date: date | None
    workflow_status: DailyBriefWorkflowStatus
    actionable_opportunities: tuple[DailyBriefOpportunity, ...]
    research_only_opportunities: tuple[DailyBriefOpportunity, ...]
    deferred_opportunities: tuple[DailyBriefOpportunity, ...]
    actionable_total_count: int
    research_only_total_count: int
    deferred_total_count: int
    research_only_limit: int | None
