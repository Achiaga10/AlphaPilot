from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from alphapilot.news.policy import (
    NewsAssessmentReason,
    NewsCoverage,
    NewsEffect,
    NewsRiskAssessment,
)
from alphapilot.news.service import NewsRefreshResult, NewsRefreshScope
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioDecision,
    PortfolioDecisionPlan,
    PortfolioFinalAction,
    PortfolioStatePosition,
)
from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
)
from alphapilot.portfolio.sizing import PortfolioDecisionReason, PortfolioDecisionType
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def news_is_advisory(strategy: StrategyName | str | None) -> bool:
    """Prospective product authority, separate from the frozen News evidence policy."""
    return strategy in {
        StrategyName.EMA20_PULLBACK,
        StrategyName.MICHO_150,
        "ema20-pullback-v1",
        "micho-150-v1",
    }


def unavailable_advisory(ticker: str, as_of: datetime) -> NewsRiskAssessment:
    return NewsRiskAssessment(
        ticker=ticker,
        as_of=as_of,
        coverage=NewsCoverage.UNAVAILABLE,
        effect=NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
        reason="News context unavailable; advisory only, with no decision authority.",
        reason_code=NewsAssessmentReason.NEWS_AGGREGATE_UNAVAILABLE,
    )


async def assess_portfolio_news(
    news: PortfolioNewsService,
    portfolio_id: UUID,
    ticker: str,
    *,
    as_of: datetime,
    advisory_only: bool,
) -> NewsRiskAssessment:
    """Persisted context only; never expose provider/parse exceptions as advice."""
    try:
        return await news.assess(portfolio_id, ticker, as_of=as_of)
    except Exception:
        if not advisory_only:
            raise
        return unavailable_advisory(ticker, as_of)


@dataclass(frozen=True, slots=True)
class PortfolioNewsGateResult:
    plan: PortfolioDecisionPlan
    refresh: NewsRefreshResult | None
    assessed_buy_tickers: tuple[str, ...]


class PortfolioNewsService(Protocol):
    async def refresh_portfolio(
        self,
        portfolio_id: UUID,
        *,
        scope: NewsRefreshScope,
        requested_tickers: tuple[str, ...],
        force_aggregate: bool = False,
    ) -> NewsRefreshResult: ...

    async def assess(
        self, portfolio_id: UUID, ticker: str, *, as_of: datetime
    ) -> NewsRiskAssessment: ...


async def apply_portfolio_news_gate(
    *,
    plan: PortfolioDecisionPlan,
    state: CurrentPortfolioState,
    portfolio_id: UUID,
    news: PortfolioNewsService,
    as_of: datetime | None = None,
    strategy_name: StrategyName | None = None,
) -> PortfolioNewsGateResult:
    """Attach persisted advisory News without changing supported strategy decisions."""
    decision_time = (as_of or datetime.now(UTC)).astimezone(UTC)

    def advisory(decision: PortfolioDecision) -> bool:
        return news_is_advisory(
            strategy_name or (decision.exit_context.strategy if decision.exit_context else None)
        )

    shortlist = tuple(
        decision.ticker
        for decision in plan.decisions
        if decision.signal is Signal.BUY and decision.is_approved_buy and not advisory(decision)
    )
    refresh = None
    if shortlist:
        refresh = await news.refresh_portfolio(
            portfolio_id,
            scope=NewsRefreshScope.CANDIDATES,
            requested_tickers=shortlist,
        )

    held = {item.ticker.upper(): item for item in state.positions}
    shortlist_set = set(shortlist)
    assessed_buys: list[str] = []
    output = []
    for decision in plan.decisions:
        original = decision.decision
        if advisory(decision):
            if not decision.is_approved_buy and decision.ticker.upper() not in held:
                output.append(
                    replace(
                        decision,
                        news_advisory_only=True,
                        news_reason="Optional News context not evaluated; no decision authority.",
                    )
                )
                continue
            assessment = await assess_portfolio_news(
                news, portfolio_id, decision.ticker, as_of=decision_time, advisory_only=True
            )
            if decision.signal is Signal.BUY:
                assessed_buys.append(decision.ticker)
            output.append(_apply_assessment(decision, assessment, held, advisory_only=True))
            continue
        if decision.signal is Signal.BUY and decision.ticker not in shortlist_set:
            output.append(
                replace(
                    decision,
                    base_decision=original,
                    final_action=PortfolioFinalAction.NOT_ACTIONABLE,
                    news_reason="News was not evaluated because a cheaper pre-News gate failed.",
                    is_final_actionable=False,
                )
            )
            continue

        assessment = await news.assess(portfolio_id, decision.ticker, as_of=decision_time)
        if decision.signal is Signal.BUY:
            assessed_buys.append(decision.ticker)
        updated = _apply_assessment(decision, assessment, held)
        output.append(updated)

    return PortfolioNewsGateResult(
        plan=replace(plan, decisions=tuple(output)),
        refresh=refresh,
        assessed_buy_tickers=tuple(assessed_buys),
    )


def _apply_assessment(
    decision: PortfolioDecision,
    assessment: NewsRiskAssessment,
    held: dict[str, PortfolioStatePosition],
    *,
    advisory_only: bool = False,
) -> PortfolioDecision:
    original = decision.decision
    updated = decision
    final_action = decision.final_action or PortfolioFinalAction.NOT_ACTIONABLE
    reason = decision.reason
    terminal_reason = decision.terminal_reason or decision.reason
    if advisory_only:
        # Preserve all authoritative and allocation fields exactly, even for
        # severe hard events, missing coverage, or previously blocked candidates.
        return replace(
            decision,
            news_advisory_only=True,
            news_effect=assessment.effect.value,
            news_coverage=assessment.coverage.value,
            news_assessment_reason=assessment.reason_code.value,
            news_aggregate_strength=(
                assessment.aggregate_strength.value if assessment.aggregate_strength else None
            ),
            news_aggregate_effect=(
                assessment.aggregate_effect.value if assessment.aggregate_effect else None
            ),
            news_targeted_review_required=assessment.targeted_review_required,
            news_reason=assessment.reason,
            news_policy_version=assessment.policy_version,
            supporting_news_article_ids=assessment.supporting_article_ids,
        )
    if original is PortfolioDecisionType.BUY and assessment.effect in {
        NewsEffect.BUY_BLOCKED,
        NewsEffect.EXIT_REQUIRED,
    }:
        updated = replace(
            updated,
            decision=PortfolioDecisionType.SKIP,
            execution_readiness=ExecutionReadiness.RESEARCH_ONLY,
            execution_readiness_reason=ExecutionReadinessReason.NEWS_RISK_BLOCK,
        )
        final_action = PortfolioFinalAction.NOT_ACTIONABLE
        reason = PortfolioDecisionReason.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE
        terminal_reason = reason
    elif original is PortfolioDecisionType.BUY and assessment.effect in {
        NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
        NewsEffect.NEWS_ASSESSMENT_PARTIAL,
    }:
        updated = replace(
            updated,
            decision=PortfolioDecisionType.SKIP,
            execution_readiness=ExecutionReadiness.UNAVAILABLE,
            execution_readiness_reason=ExecutionReadinessReason.NEWS_ASSESSMENT_UNAVAILABLE,
        )
        final_action = PortfolioFinalAction.NOT_ACTIONABLE
        reason = _unavailable_reason(assessment.reason_code)
        terminal_reason = reason
    elif assessment.effect is NewsEffect.EXIT_REQUIRED and decision.ticker.upper() in held:
        position = held[decision.ticker.upper()]
        updated = replace(
            updated,
            decision=PortfolioDecisionType.SELL,
            current_shares=position.shares,
            estimated_proceeds=position.market_value,
        )
        final_action = PortfolioFinalAction.EXIT_REQUIRED
        reason = PortfolioDecisionReason.NEWS_RISK_EXIT
        terminal_reason = reason
    return replace(
        updated,
        reason=reason,
        base_decision=original,
        allocation_reason=decision.allocation_reason or decision.reason,
        terminal_reason=terminal_reason,
        news_effect=assessment.effect.value,
        news_coverage=assessment.coverage.value,
        news_assessment_reason=assessment.reason_code.value,
        news_aggregate_strength=(
            assessment.aggregate_strength.value if assessment.aggregate_strength else None
        ),
        news_aggregate_effect=(
            assessment.aggregate_effect.value if assessment.aggregate_effect else None
        ),
        news_targeted_review_required=assessment.targeted_review_required,
        final_action=final_action,
        news_reason=assessment.reason,
        news_policy_version=assessment.policy_version,
        supporting_news_article_ids=assessment.supporting_article_ids,
        is_final_actionable=(
            (
                updated.decision is PortfolioDecisionType.BUY
                and updated.execution_readiness is ExecutionReadiness.ACTIONABLE
                and final_action is PortfolioFinalAction.BUY
            )
            or (
                updated.decision is PortfolioDecisionType.SELL
                and final_action in {PortfolioFinalAction.SELL, PortfolioFinalAction.EXIT_REQUIRED}
                and updated.current_shares > 0
            )
        ),
    )


def _unavailable_reason(reason: NewsAssessmentReason) -> PortfolioDecisionReason:
    mapping = {
        NewsAssessmentReason.NEWS_AGGREGATE_UNAVAILABLE: (
            PortfolioDecisionReason.NEWS_AGGREGATE_UNAVAILABLE
        ),
        NewsAssessmentReason.NEWS_AGGREGATE_STALE: PortfolioDecisionReason.NEWS_AGGREGATE_STALE,
        NewsAssessmentReason.NEWS_WEAK_EVIDENCE: PortfolioDecisionReason.NEWS_WEAK_EVIDENCE,
        NewsAssessmentReason.TARGETED_NEWS_REVIEW_REQUIRED: (
            PortfolioDecisionReason.TARGETED_NEWS_REVIEW_REQUIRED
        ),
        NewsAssessmentReason.ATTRIBUTABLE_NEWS_UNAVAILABLE: (
            PortfolioDecisionReason.ATTRIBUTABLE_NEWS_UNAVAILABLE
        ),
        NewsAssessmentReason.GEMINI_REQUIRED_BUT_UNAVAILABLE: (
            PortfolioDecisionReason.GEMINI_REQUIRED_BUT_UNAVAILABLE
        ),
    }
    return mapping.get(reason, PortfolioDecisionReason.NEWS_ASSESSMENT_UNAVAILABLE)
