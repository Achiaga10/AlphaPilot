from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.news.external_sentiment import assess_external_sentiment
from alphapilot.news.policy import NewsEffect
from alphapilot.news.service import NewsService
from alphapilot.portfolio.daily_brief import (
    DailyBriefDataStatus,
    DailyBriefOpportunities,
    DailyBriefOpportunity,
    DailyBriefPosition,
    DailyBriefReadiness,
    DailyBriefReference,
    DailyBriefSummary,
    DailyBriefWorkflowStatus,
    DailyPortfolioBrief,
    DailyPortfolioBriefCore,
)
from alphapilot.portfolio.decisions import CurrentPortfolioState, PortfolioStatePosition
from alphapilot.portfolio.execution_readiness import classify_new_buy
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.stop_exit_guidance import StopExitGuidanceService
from alphapilot.services.admin_data import ResearchDataSummaryService
from alphapilot.services.daily_market_scheduler import DailySchedulerStatus, DailySyncStatus
from alphapilot.services.position_intelligence import PositionIntelligenceService
from alphapilot.services.research_portfolio import ResearchPortfolioService
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.profile import list_strategy_profiles


class DailyPortfolioBriefService:
    """Compose authoritative daily facts without persisting or recalculating them."""

    def __init__(
        self,
        portfolios: ResearchPortfolioService,
        intelligence: PositionIntelligenceService,
        orchestrator: PortfolioDecisionOrchestrator,
        freshness: ResearchDataSummaryService,
        scheduler_status: DailySchedulerStatus,
        news: NewsService | None = None,
    ) -> None:
        self.portfolios = portfolios
        self.intelligence = intelligence
        self.orchestrator = orchestrator
        self.freshness = freshness
        self.scheduler_status = scheduler_status
        self.news = news
        self.guidance = StopExitGuidanceService()
        self.session_policy = getattr(orchestrator, "session_policy", CompletedDailySessionPolicy())

    async def build_core(
        self, portfolio_id: UUID, *, requested_as_of_date: date | None = None
    ) -> DailyPortfolioBriefCore:
        valuation = await self.portfolios.value(portfolio_id)
        data = await self.freshness.get_freshness()
        brief_day = data.latest_spy_date
        expected_day = self._expected_completed_session()
        blockers: list[str] = []
        positions: list[DailyBriefPosition] = []
        intelligence = {
            item.position_id: item
            for item in await self.intelligence.get_portfolio_intelligence(
                portfolio_id, valuation=valuation
            )
        }
        for valued in valuation.positions:
            intel = intelligence[valued.position_id]
            guide = self.guidance.build(intel)
            status = intel.monitoring_status or "UNAVAILABLE"
            base_status = status
            position_reason = intel.monitoring_reason
            news_effect = NewsEffect.NO_EFFECT
            news_coverage = "NEVER_REFRESHED"
            news_reason: str | None = None
            news_policy_version: str | None = None
            supporting_news_article_ids: tuple[UUID, ...] = ()
            aggregate = None
            aggregate_assessment = None
            explanation = intel.explanation
            if self.news is not None and intel.monitoring_completed_trading_day is not None:
                aggregate = await self.news.latest_sentiment_observation(
                    portfolio_id, intel.ticker, as_of=datetime.now(UTC)
                )
                aggregate_assessment = assess_external_sentiment(
                    self.news.observation_snapshot(aggregate) if aggregate else None,
                    as_of=datetime.now(UTC),
                )
                assessment = await self.news.assess(
                    portfolio_id,
                    intel.ticker,
                    as_of=datetime.now(UTC),
                )
                news_effect = assessment.effect
                news_coverage = assessment.coverage.value
                news_reason = assessment.reason
                news_policy_version = assessment.policy_version
                supporting_news_article_ids = assessment.supporting_article_ids
                if base_status != "SELL" and news_effect is NewsEffect.EXIT_REQUIRED:
                    status = "SELL"
                    position_reason = "NEWS_RISK_EXIT"
                    explanation = f"News risk exit: {assessment.reason}"
                elif base_status == "HOLD" and news_effect in {
                    NewsEffect.ATTENTION,
                    NewsEffect.BUY_BLOCKED,
                    NewsEffect.NEWS_ASSESSMENT_PARTIAL,
                }:
                    status = "ATTENTION"
                    explanation = f"News attention: {assessment.reason}"
            positions.append(
                DailyBriefPosition(
                    position_id=intel.position_id,
                    ticker=intel.ticker,
                    company_name=intel.company_name,
                    strategy=intel.strategy,
                    strategy_profile_id=intel.strategy_profile_id,
                    strategy_profile_version=intel.strategy_profile_version,
                    status=status,
                    reason=position_reason,
                    explanation=explanation,
                    quantity=intel.quantity,
                    latest_completed_close=intel.latest_completed_close,
                    unrealized_pnl=intel.unrealized_pnl,
                    unrealized_pnl_pct=intel.unrealized_pnl_pct,
                    as_of_session=intel.monitoring_completed_trading_day,
                    sticky_sell=intel.exit_triggered,
                    exit_triggered_on=intel.exit_triggered_on,
                    loss_control_policy=guide.loss_control_policy,
                    loss_control_boundary=guide.current_loss_control_boundary,
                    loss_control_trigger=guide.loss_control_trigger,
                    broker_stop_order=guide.broker_stop_order,
                    references=tuple(
                        DailyBriefReference(
                            item.reference_type.value,
                            item.value,
                            item.condition,
                            item.qualifier,
                            item.distance_dollars,
                            item.distance_pct,
                        )
                        for item in guide.references
                    ),
                    base_status=base_status,
                    news_effect=news_effect.value,
                    news_coverage=news_coverage,
                    final_status=status,
                    news_reason=news_reason,
                    news_policy_version=news_policy_version,
                    supporting_news_article_ids=supporting_news_article_ids,
                    aggregate_sentiment_score=(aggregate.sentiment_score if aggregate else None),
                    aggregate_bullish_pct=(aggregate.bullish_pct if aggregate else None),
                    aggregate_bearish_pct=(aggregate.bearish_pct if aggregate else None),
                    aggregate_mentions=(aggregate.mentions if aggregate else None),
                    aggregate_source_count=(aggregate.source_count if aggregate else None),
                    aggregate_buzz_score=(aggregate.buzz_score if aggregate else None),
                    aggregate_trend=(aggregate.trend if aggregate else None),
                    aggregate_observed_at=(aggregate.observed_at if aggregate else None),
                    aggregate_evidence_strength=(
                        aggregate_assessment.strength.value
                        if aggregate_assessment
                        else "UNAVAILABLE"
                    ),
                    aggregate_effect=(
                        aggregate_assessment.effect.value if aggregate_assessment else "UNAVAILABLE"
                    ),
                    aggregate_limitation=(
                        aggregate_assessment.limitation if aggregate_assessment else None
                    ),
                )
            )
        positions.sort(key=lambda item: item.ticker)
        required = tuple(item for item in positions if item.status == "SELL" or item.sticky_sell)
        attention = tuple(
            item for item in positions if item.status == "ATTENTION" and not item.sticky_sell
        )
        hold = tuple(item for item in positions if item.status == "HOLD" and not item.sticky_sell)
        unavailable = tuple(item for item in positions if item.status == "UNAVAILABLE")

        readiness = DailyBriefReadiness.READY
        if brief_day is None:
            readiness = DailyBriefReadiness.BLOCKED
            blockers.append("NO_COMPLETED_SPY_SESSION")
        elif brief_day < expected_day:
            readiness = DailyBriefReadiness.BLOCKED
            blockers.append("EXPECTED_COMPLETED_SESSION_NOT_STORED")
        if self.scheduler_status.last_status == DailySyncStatus.FAILED:
            readiness = DailyBriefReadiness.BLOCKED
            blockers.append("LATEST_DAILY_SYNC_FAILED")
        if valuation.valuation_status.value != "COMPLETE":
            readiness = DailyBriefReadiness.BLOCKED
            blockers.append("PORTFOLIO_FACTS_INCOMPLETE")
        elif unavailable:
            readiness = DailyBriefReadiness.DEGRADED
            blockers.append("PORTFOLIO_GUIDANCE_INCOMPLETE")
        if data.stale_tracked_ticker_count or data.no_data_tracked_ticker_count:
            if readiness != DailyBriefReadiness.BLOCKED:
                readiness = DailyBriefReadiness.DEGRADED
            blockers.append("TRACKED_MARKET_DATA_INCOMPLETE")
        if any(
            item.as_of_session is not None
            and brief_day is not None
            and item.as_of_session < brief_day
            for item in positions
        ):
            if readiness != DailyBriefReadiness.BLOCKED:
                readiness = DailyBriefReadiness.DEGRADED
            blockers.append("POSITION_GUIDANCE_STALE")

        workflow = DailyBriefWorkflowStatus.READY_FOR_REVIEW
        if readiness == DailyBriefReadiness.BLOCKED:
            workflow = DailyBriefWorkflowStatus.NEW_ENTRIES_BLOCKED
        elif required:
            workflow = DailyBriefWorkflowStatus.WAITING_FOR_REQUIRED_EXITS
            blockers.append("REQUIRED_EXITS_MUST_BE_RESOLVED_FIRST")

        return DailyPortfolioBriefCore(
            portfolio_id=portfolio_id,
            portfolio_revision=valuation.revision,
            generated_at=datetime.now(UTC),
            data_status=DailyBriefDataStatus(
                readiness,
                expected_day,
                data.latest_spy_date,
                brief_day,
                self.scheduler_status.last_status.value,
                self._data_explanation(readiness),
            ),
            workflow_status=workflow,
            summary=DailyBriefSummary(
                valuation.total_equity,
                valuation.cash,
                valuation.positions_market_value,
                valuation.cash_pct,
                len(valuation.positions),
                PortfolioRiskConfig().max_positions,
                valuation.valuation_status.value,
                (
                    sum(
                        (item.modeled_risk_dollars for item in valuation.positions),
                        Decimal("0"),
                    )
                    if all(item.modeled_risk_dollars > 0 for item in valuation.positions)
                    else None
                ),
            ),
            required_actions=required,
            attention_positions=attention,
            hold_positions=hold,
            unavailable_positions=unavailable,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    async def build_opportunities(
        self,
        portfolio_id: UUID,
        *,
        requested_as_of_date: date | None = None,
        research_only_limit: int | None = 10,
    ) -> DailyBriefOpportunities:
        core = await self.build_core(portfolio_id, requested_as_of_date=requested_as_of_date)
        return await self._build_opportunities_from_core(
            core,
            requested_as_of_date=requested_as_of_date,
            research_only_limit=research_only_limit,
        )

    async def build(
        self, portfolio_id: UUID, *, requested_as_of_date: date | None = None
    ) -> DailyPortfolioBrief:
        """Compatibility composition used by grounded Copilot and lower-level callers."""
        core = await self.build_core(portfolio_id, requested_as_of_date=requested_as_of_date)
        opportunities = await self._build_opportunities_from_core(
            core,
            requested_as_of_date=requested_as_of_date,
            research_only_limit=None,
        )
        return DailyPortfolioBrief(
            core.portfolio_id,
            core.portfolio_revision,
            core.generated_at,
            core.data_status,
            core.workflow_status,
            core.summary,
            core.required_actions,
            core.attention_positions,
            opportunities.actionable_opportunities,
            opportunities.research_only_opportunities,
            opportunities.deferred_opportunities,
            core.hold_positions,
            core.unavailable_positions,
            core.blockers,
        )

    async def _build_opportunities_from_core(
        self,
        core: DailyPortfolioBriefCore,
        *,
        requested_as_of_date: date | None,
        research_only_limit: int | None,
    ) -> DailyBriefOpportunities:
        if research_only_limit is not None and research_only_limit < 0:
            raise ValueError("research_only_limit must not be negative")
        actionable: list[DailyBriefOpportunity] = []
        research_only: list[DailyBriefOpportunity] = []
        deferred: list[DailyBriefOpportunity] = []
        analysis_day: date | None = core.data_status.brief_session
        if (
            core.data_status.brief_session is not None
            and core.summary.valuation_readiness == "COMPLETE"
            and core.data_status.readiness != DailyBriefReadiness.BLOCKED
        ):
            valuation = await self.portfolios.value(core.portfolio_id)
            if valuation.revision != core.portfolio_revision:
                raise ValueError("Portfolio revision changed while building Daily Brief")
            state = CurrentPortfolioState(
                valuation.cash,
                tuple(
                    PortfolioStatePosition(
                        item.ticker,
                        item.quantity,
                        item.latest_completed_close,
                        item.cost_basis,
                        item.sector,
                        item.modeled_risk_dollars,
                    )
                    for item in valuation.positions
                    if item.latest_completed_close is not None
                ),
            )
            effective_day = requested_as_of_date or core.data_status.brief_session
            snapshot = await self.orchestrator.load_market_snapshot(
                state=state,
                requested_as_of_date=effective_day,
            )
            analysis_day = snapshot.analysis_as_of_date
            for profile in list_strategy_profiles():
                result = await self.orchestrator.build_plan(
                    state=state,
                    strategy_name=profile.strategy,
                    selection_policy=profile.recommended_selection_policy,
                    sizing_policy=profile.sizing_policy,
                    risk_config=PortfolioRiskConfig(),
                    requested_as_of_date=effective_day,
                    exit_mode=profile.ema_exit_mode or TrendExitMode.HYBRID,
                    hybrid_trend_threshold_pct=profile.hybrid_trend_threshold_pct or Decimal("2"),
                    micho_entry_mode=profile.micho_entry_mode or MichoEntryMode.BOTH,
                    evaluate_existing_position_exits=False,
                    market_snapshot=snapshot,
                )
                plan_id = self._plan_id(
                    core.portfolio_id,
                    valuation.revision,
                    profile.profile_id,
                    profile.version,
                    result.analysis_as_of_date,
                )
                for decision in result.plan.decisions:
                    if decision.signal.value != "BUY":
                        continue
                    opportunity = self._opportunity(
                        decision,
                        profile.profile_id,
                        profile.version,
                        profile.strategy.value,
                        profile.sizing_policy.value,
                        profile.recommended_selection_policy,
                        plan_id,
                        valuation.revision,
                        result.analysis_as_of_date,
                    )
                    news_blocked = False
                    if self.news is not None:
                        assessment = await self.news.assess(
                            core.portfolio_id,
                            decision.ticker,
                            as_of=datetime.now(UTC),
                        )
                        opportunity = replace(
                            opportunity,
                            base_decision=decision.decision.value,
                            news_coverage=assessment.coverage.value,
                            news_effect=assessment.effect.value,
                            final_decision=decision.decision.value,
                            news_reason=assessment.reason,
                            news_policy_version=assessment.policy_version,
                            supporting_news_article_ids=assessment.supporting_article_ids,
                        )
                        if assessment.effect in {
                            NewsEffect.BUY_BLOCKED,
                            NewsEffect.EXIT_REQUIRED,
                            NewsEffect.NEWS_ASSESSMENT_PARTIAL,
                            NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
                        }:
                            news_blocked = True
                            opportunity = replace(
                                opportunity,
                                decision="SKIP",
                                decision_reason=assessment.effect.value,
                                execution_readiness="UNAVAILABLE",
                                execution_readiness_reason=(
                                    "NEWS_RISK_BLOCK"
                                    if assessment.effect
                                    in {NewsEffect.BUY_BLOCKED, NewsEffect.EXIT_REQUIRED}
                                    else "NEWS_ASSESSMENT_UNAVAILABLE"
                                ),
                                final_decision="DO_NOT_BUY",
                                workflow_status="NEWS_BLOCKED",
                            )
                    if profile.profile_id == "ema20-pullback-v1":
                        readiness_value, readiness_reason = classify_new_buy(None)
                        opportunity = replace(
                            opportunity,
                            execution_readiness=readiness_value.value,
                            execution_readiness_reason=readiness_reason.value,
                        )
                    if news_blocked:
                        deferred.append(opportunity)
                    elif opportunity.execution_readiness == "RESEARCH_ONLY":
                        research_only.append(opportunity)
                    elif decision.decision.value != "BUY":
                        deferred.append(
                            replace(
                                opportunity,
                                workflow_status="PORTFOLIO_CONSTRAINT_BLOCKED",
                            )
                        )
                    elif decision.execution_readiness.value == "ACTIONABLE":
                        actionable.append(opportunity)
                    else:
                        deferred.append(opportunity)

        actionable = self._ordered(actionable)
        research_only = self._ordered(research_only)
        deferred = self._ordered(deferred)
        if core.workflow_status != DailyBriefWorkflowStatus.READY_FOR_REVIEW:
            deferred.extend(
                replace(item, workflow_status=core.workflow_status.value) for item in actionable
            )
            actionable.clear()
        research_total = len(research_only)
        displayed_research = (
            research_only if research_only_limit is None else research_only[:research_only_limit]
        )
        return DailyBriefOpportunities(
            core.portfolio_id,
            core.portfolio_revision,
            datetime.now(UTC),
            analysis_day,
            core.workflow_status,
            tuple(actionable),
            tuple(displayed_research),
            tuple(deferred),
            len(actionable),
            research_total,
            len(deferred),
            research_only_limit,
        )

    @staticmethod
    def _opportunity(
        decision: object,
        profile_id: str,
        profile_version: int,
        strategy: str,
        sizing: str,
        selection: SelectionPolicyName,
        plan_id: str,
        revision: int,
        analysis_day: date,
    ) -> DailyBriefOpportunity:
        from alphapilot.portfolio.decisions import PortfolioDecision

        assert isinstance(decision, PortfolioDecision)
        boundary = decision.loss_control_boundary_price
        if decision.execution_readiness.value == "ACTIONABLE" and (
            boundary is None or boundary <= 0 or not decision.loss_control_trigger
        ):
            raise ValueError(
                "ACTIONABLE opportunity lacks deterministic numeric loss-control evidence"
            )
        distance = decision.reference_price - boundary if boundary is not None else None
        distance_pct = (
            distance / decision.reference_price * Decimal("100")
            if distance is not None and distance > 0 and decision.reference_price > 0
            else None
        )
        references: list[DailyBriefReference] = []
        context = decision.exit_context
        if context is not None:
            raw_references = (
                (
                    "EMA20_PULLBACK_REFERENCE",
                    context.ema20,
                    "CONDITIONAL_EXIT_REFERENCE",
                    "Conditional EMA20 reference; not an approved loss-control boundary",
                ),
                (
                    "EMA50_HARD_BREAKDOWN",
                    context.ema50,
                    "COMPLETED_DAILY_CLOSE_BELOW",
                    "Hard trend-exit reference; not an approved loss-control boundary",
                ),
                (
                    "SMA150_BREAKDOWN",
                    context.sma150,
                    "COMPLETED_DAILY_CLOSE_BELOW",
                    "Micho completed-close exit and approved loss-control boundary",
                ),
            )
            for reference_type, value, condition, qualifier in raw_references:
                if value is None:
                    continue
                reference_distance = decision.reference_price - value
                reference_distance_pct = (
                    reference_distance / decision.reference_price * Decimal("100")
                    if decision.reference_price > 0
                    else None
                )
                references.append(
                    DailyBriefReference(
                        reference_type,
                        value,
                        condition,
                        qualifier,
                        reference_distance,
                        reference_distance_pct,
                    )
                )
        return DailyBriefOpportunity(
            decision.ticker,
            strategy,
            profile_id,
            profile_version,
            plan_id,
            revision,
            selection.value,
            sizing,
            decision.decision.value,
            decision.reason.value,
            decision.ranking_score,
            decision.reference_price,
            decision.proposed_shares,
            decision.target_allocation_dollars,
            decision.target_weight_pct,
            decision.sector,
            decision.execution_readiness.value,
            decision.execution_readiness_reason.value,
            decision.loss_control_policy,
            boundary,
            decision.loss_control_trigger,
            distance if distance is not None and distance > 0 else None,
            distance_pct,
            decision.loss_control_broker_stop_order,
            tuple(references),
            analysis_day,
            decision.action_id,
            "READY_FOR_REVIEW",
        )

    @staticmethod
    def _ordered(items: list[DailyBriefOpportunity]) -> list[DailyBriefOpportunity]:
        return sorted(
            items,
            key=lambda item: (
                item.ranking_score is None,
                -(item.ranking_score or Decimal("0")),
                item.ticker,
            ),
        )

    @staticmethod
    def _plan_id(
        portfolio_id: UUID, revision: int, profile_id: str, version: int, day: date
    ) -> str:
        payload = [str(portfolio_id), revision, profile_id, version, day.isoformat()]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:24]

    @staticmethod
    def _data_explanation(readiness: DailyBriefReadiness) -> str:
        if readiness == DailyBriefReadiness.READY:
            return "Stored facts are aligned to the latest completed SPY session."
        if readiness == DailyBriefReadiness.DEGRADED:
            return "Some stored facts are incomplete or stale; inspect each actual as-of date."
        return "Current new-entry decisions are blocked until completed-session data is ready."

    def _expected_completed_session(self) -> date:
        """Return the conservative latest possible U.S. weekday session."""
        candidate = self.session_policy.completed_through()
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
        return candidate
