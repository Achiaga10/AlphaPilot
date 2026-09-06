from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from alphapilot.news.external_sentiment import (
    AggregateEvidenceStrength,
    AggregateSentimentEffect,
)
from alphapilot.news.policy import (
    NewsAssessmentReason,
    NewsCoverage,
    NewsEffect,
    NewsRiskAssessment,
)
from alphapilot.news.service import NewsRefreshResult, NewsRefreshScope
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
    PortfolioFinalAction,
)
from alphapilot.portfolio.exit_guidance import StrategyExitContext, StrategyExitState
from alphapilot.portfolio.news_gate import apply_portfolio_news_gate
from alphapilot.portfolio.orchestration import (
    BuyFunnelStage,
    CandidateDataStatus,
    CandidateOrchestrationStatus,
    PortfolioDecisionOrchestrator,
)
from alphapilot.portfolio.sizing import (
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingPolicyName,
)
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def micho_exit() -> StrategyExitContext:
    return StrategyExitContext(
        strategy=StrategyName.MICHO_150,
        data_as_of_date=date(2026, 9, 2),
        reference_close=Decimal("100"),
        current_signal=Signal.BUY,
        signal_reason="MICHO_BREAKOUT",
        exit_mode="close-below-sma150",
        current_exit_state=StrategyExitState.ABOVE_SMA150,
        sma150=Decimal("90"),
    )


class FakeNews:
    def __init__(self, assessment: NewsRiskAssessment) -> None:
        self.assessment = assessment
        self.refreshes: list[tuple[str, ...]] = []
        self.assessments: list[str] = []

    async def refresh_portfolio(
        self, portfolio_id, *, scope, requested_tickers, force_aggregate=False
    ) -> NewsRefreshResult:
        _ = force_aggregate
        self.refreshes.append(tuple(requested_tickers))
        return NewsRefreshResult(
            portfolio_id=portfolio_id,
            tickers=tuple(requested_tickers),
            fetched=0,
            inserted=0,
            duplicates=0,
            classified=0,
            classification_failures=0,
            provider_failures=(),
            refreshed_at=datetime.now(UTC),
            scope=NewsRefreshScope(scope),
            coverage=tuple((ticker, NewsCoverage.CURRENT) for ticker in requested_tickers),
            aggregate_reused=tuple(requested_tickers),
        )

    async def assess(self, portfolio_id, ticker, *, as_of) -> NewsRiskAssessment:
        _ = (portfolio_id, as_of)
        self.assessments.append(ticker)
        return self.assessment


def assessment(
    *,
    effect: NewsEffect = NewsEffect.NO_EFFECT,
    reason: NewsAssessmentReason = NewsAssessmentReason.NO_ADVERSE_AGGREGATE_EVIDENCE,
) -> NewsRiskAssessment:
    return NewsRiskAssessment(
        ticker="AAA",
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
        coverage=NewsCoverage.CURRENT,
        effect=effect,
        reason=reason.value,
        reason_code=reason,
        aggregate_strength=AggregateEvidenceStrength.SUFFICIENT,
        aggregate_effect=AggregateSentimentEffect.MIXED_OR_NEUTRAL,
    )


def status(ticker: str) -> CandidateOrchestrationStatus:
    return CandidateOrchestrationStatus(
        ticker=ticker,
        status=CandidateDataStatus.READY,
        data_as_of_date=date(2026, 9, 2),
        signal=Signal.BUY,
        reason="TEST_BUY",
    )


@pytest.mark.asyncio
async def test_news_gate_refreshes_only_actionable_ranked_shortlist_and_funnel_reconciles() -> None:
    portfolio_id = uuid4()
    context = micho_exit()
    state = CurrentPortfolioState(Decimal("100000"))
    plan = PortfolioDecisionEngine().build_plan(
        state,
        (
            PortfolioCandidate(
                "ACTION", Signal.BUY, Decimal("100"), Decimal("4"), exit_context=context
            ),
            PortfolioCandidate(
                "EXCLUDED",
                Signal.BUY,
                Decimal("100"),
                Decimal("3"),
                pre_decision_reason=(PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS),
                exit_context=context,
            ),
            PortfolioCandidate(
                "EXTENDED",
                Signal.BUY,
                Decimal("100"),
                Decimal("2"),
                pre_decision_reason=PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20,
                exit_context=context,
            ),
            PortfolioCandidate("NOLOSS", Signal.BUY, Decimal("100"), Decimal("1")),
        ),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    news = FakeNews(assessment())

    result = await apply_portfolio_news_gate(
        plan=plan,
        state=state,
        portfolio_id=portfolio_id,
        news=news,
        as_of=datetime(2026, 9, 2, tzinfo=UTC),
    )
    readiness = PortfolioDecisionOrchestrator.final_readiness(
        tuple(status(ticker) for ticker in ("ACTION", "EXCLUDED", "EXTENDED", "NOLOSS")),
        result.plan,
    )
    groups = {group.stage: group for group in readiness.buy_funnel.groups}

    assert news.refreshes == [("ACTION",)]
    assert news.assessments == ["ACTION"]
    assert result.assessed_buy_tickers == ("ACTION",)
    assert groups[BuyFunnelStage.FINAL_APPROVED_BUY].tickers == ("ACTION",)
    assert groups[BuyFunnelStage.USER_EXCLUDED].tickers == ("EXCLUDED",)
    assert groups[BuyFunnelStage.EMA20_ENTRY_SAFETY_BLOCKED].tickers == ("EXTENDED",)
    assert groups[BuyFunnelStage.LOSS_CONTROL_UNAVAILABLE].tickers == ("NOLOSS",)
    decisions = {item.ticker: item for item in result.plan.decisions}
    assert decisions["EXCLUDED"].terminal_reason is (
        PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS
    )
    assert decisions["EXTENDED"].terminal_reason is (
        PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
    )
    assert decisions["NOLOSS"].terminal_reason is (PortfolioDecisionReason.LOSS_CONTROL_UNAVAILABLE)
    assert all(
        decisions[ticker].final_action is PortfolioFinalAction.NOT_ACTIONABLE
        for ticker in ("EXCLUDED", "EXTENDED", "NOLOSS")
    )
    assert readiness.buy_funnel.technical_buy_signals == sum(
        group.count for group in readiness.buy_funnel.groups
    )
    assert readiness.buy_funnel.rejected_before_news == 3
    assert readiness.buy_funnel.reached_news == 1
    assert readiness.buy_funnel.final_approved_buys == 1


@pytest.mark.asyncio
async def test_actual_adverse_and_provider_unavailability_have_distinct_reasons() -> None:
    portfolio_id = uuid4()
    context = micho_exit()
    state = CurrentPortfolioState(Decimal("100000"))
    base = PortfolioDecisionEngine().build_plan(
        state,
        (PortfolioCandidate("AAA", Signal.BUY, Decimal("100"), exit_context=context),),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )

    adverse = await apply_portfolio_news_gate(
        plan=base,
        state=state,
        portfolio_id=portfolio_id,
        news=FakeNews(
            assessment(
                effect=NewsEffect.BUY_BLOCKED,
                reason=NewsAssessmentReason.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE,
            )
        ),
    )
    unavailable = await apply_portfolio_news_gate(
        plan=base,
        state=state,
        portfolio_id=portfolio_id,
        news=FakeNews(
            assessment(
                effect=NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
                reason=NewsAssessmentReason.NEWS_AGGREGATE_UNAVAILABLE,
            )
        ),
    )

    assert adverse.plan.decisions[0].reason is (
        PortfolioDecisionReason.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE
    )
    assert unavailable.plan.decisions[0].reason is (
        PortfolioDecisionReason.NEWS_AGGREGATE_UNAVAILABLE
    )
    assert adverse.plan.decisions[0].decision is PortfolioDecisionType.SKIP
    assert unavailable.plan.decisions[0].decision is PortfolioDecisionType.SKIP
    assert adverse.plan.decisions[0].terminal_reason is (
        PortfolioDecisionReason.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE
    )
    assert unavailable.plan.decisions[0].terminal_reason is (
        PortfolioDecisionReason.NEWS_AGGREGATE_UNAVAILABLE
    )
    assert adverse.plan.decisions[0].final_action is PortfolioFinalAction.NOT_ACTIONABLE
    assert unavailable.plan.decisions[0].final_action is PortfolioFinalAction.NOT_ACTIONABLE
