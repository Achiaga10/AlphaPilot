"""Product authority tests; synthetic approved risk is NOT a new EMA stop policy."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from alphapilot.news.policy import NewsCoverage, NewsEffect, NewsRiskAssessment
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
    PortfolioFinalAction,
    PortfolioStatePosition,
)
from alphapilot.portfolio.entry_safety import (
    Ema20EntryPriceSource,
    assess_ema20_entry_safety,
)
from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
    LossControlSource,
)
from alphapilot.portfolio.exit_guidance import StrategyExitContext, StrategyExitState
from alphapilot.portfolio.news_gate import apply_portfolio_news_gate
from alphapilot.portfolio.orchestration import (
    CandidateDataStatus,
    CandidateOrchestrationStatus,
    PortfolioDecisionOrchestrator,
)
from alphapilot.portfolio.sizing import (
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingPolicyName,
)
from alphapilot.schemas.portfolio import PortfolioDecisionSchema
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal

NOW = datetime(2026, 9, 2, 22, tzinfo=UTC)
DAY = date(2026, 9, 2)


def strategy_context(strategy=StrategyName.EMA20_PULLBACK, signal=Signal.BUY):
    micho = strategy is StrategyName.MICHO_150
    return StrategyExitContext(
        strategy=strategy,
        data_as_of_date=DAY,
        reference_close=Decimal("100"),
        current_signal=signal,
        signal_reason="TEST",
        exit_mode="close-below-sma150" if micho else "hybrid",
        current_exit_state=(
            StrategyExitState.ABOVE_SMA150 if micho else StrategyExitState.ABOVE_EMA20
        ),
        ema20=None if micho else Decimal("100"),
        ema50=None if micho else Decimal("95"),
        sma150=Decimal("90") if micho else None,
    )


def base_plan(state, *candidates):
    candidates = tuple(
        replace(
            candidate,
            entry_safety=assess_ema20_entry_safety(
                ticker=candidate.ticker,
                as_of=NOW,
                entry_price=candidate.reference_price,
                entry_price_source=Ema20EntryPriceSource.COMPLETED_SESSION_CLOSE,
                entry_price_timestamp=NOW,
                ema20=Decimal("100"),
                ema20_as_of=DAY,
            ),
        )
        if candidate.exit_context is not None
        and candidate.exit_context.strategy is StrategyName.EMA20_PULLBACK
        and candidate.entry_safety is None
        else candidate
        for candidate in candidates
    )
    return PortfolioDecisionEngine().build_plan(
        state,
        candidates,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )


def approved_test_boundary(decision):
    # Inject only at the orchestration boundary. No real profile receives this.
    return replace(
        decision,
        reason=PortfolioDecisionReason.BUY_APPROVED,
        terminal_reason=PortfolioDecisionReason.BUY_APPROVED,
        execution_readiness=ExecutionReadiness.ACTIONABLE,
        execution_readiness_reason=ExecutionReadinessReason.LOSS_CONTROL_READY,
        loss_control_policy="TEST_ONLY_APPROVED_BOUNDARY",
        loss_control_boundary_price=Decimal("95"),
        loss_control_active=True,
        loss_control_trigger="TEST_COMPLETED_CLOSE_BELOW",
        loss_control_source=LossControlSource.APPROVED_SYSTEM_POLICY,
        manual_stop_required=False,
        final_action=PortfolioFinalAction.BUY,
        is_final_actionable=True,
    )


class PersistedNews:
    def __init__(self, effect=NewsEffect.NO_EFFECT, coverage=NewsCoverage.CURRENT, error=None):
        self.effect, self.coverage, self.error = effect, coverage, error
        self.reads = []
        self.refreshes = 0

    async def refresh_portfolio(self, *args, **kwargs):
        self.refreshes += 1
        raise AssertionError("Approval must not require any News provider refresh")

    async def assess(self, portfolio_id, ticker, *, as_of):
        self.reads.append(ticker)
        if self.error:
            raise self.error
        return NewsRiskAssessment(
            ticker=ticker,
            as_of=as_of,
            effect=self.effect,
            coverage=self.coverage,
            reason="Stored adverse event" if self.effect != NewsEffect.NO_EFFECT else "No articles",
            supporting_article_ids=(uuid4(),) if self.effect == NewsEffect.EXIT_REQUIRED else (),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", [StrategyName.EMA20_PULLBACK, StrategyName.MICHO_150])
@pytest.mark.parametrize(
    ("effect", "coverage"),
    [
        (NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE, NewsCoverage.UNAVAILABLE),
        (NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE, NewsCoverage.STALE),
        (NewsEffect.NEWS_ASSESSMENT_PARTIAL, NewsCoverage.PARTIAL),
        (NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE, NewsCoverage.RATE_LIMITED),
        (NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE, NewsCoverage.NEVER_REFRESHED),
        (NewsEffect.NO_EFFECT, NewsCoverage.CURRENT),
        (NewsEffect.BUY_BLOCKED, NewsCoverage.CURRENT),
        (NewsEffect.EXIT_REQUIRED, NewsCoverage.CURRENT),
    ],
)
async def test_all_news_evidence_is_advisory_for_otherwise_approved_buy(strategy, effect, coverage):
    state = CurrentPortfolioState(Decimal("100000"))
    plan = base_plan(
        state,
        PortfolioCandidate(
            "AAA", Signal.BUY, Decimal("100"), exit_context=strategy_context(strategy)
        ),
    )
    original = approved_test_boundary(plan.decisions[0])
    news = PersistedNews(effect, coverage)
    result = await apply_portfolio_news_gate(
        plan=replace(plan, decisions=(original,)),
        state=state,
        portfolio_id=uuid4(),
        news=news,
        as_of=NOW,
        strategy_name=strategy,
    )
    decision = result.plan.decisions[0]
    assert decision.is_approved_buy
    assert decision.final_action is PortfolioFinalAction.BUY
    assert decision.terminal_reason == original.terminal_reason
    assert decision.reason == original.reason
    assert decision.target_allocation_dollars == original.target_allocation_dollars
    assert decision.proposed_shares == original.proposed_shares
    assert decision.execution_readiness == original.execution_readiness
    assert decision.news_effect == effect.value
    assert decision.news_coverage == coverage.value
    assert decision.news_advisory_only
    assert news.refreshes == 0 and result.refresh is None
    assert result.assessed_buy_tickers == ("AAA",)  # persisted advisory context was read
    assert PortfolioDecisionSchema.model_validate(decision).model_dump(mode="json")[
        "news_advisory_only"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", [StrategyName.EMA20_PULLBACK, StrategyName.MICHO_150])
@pytest.mark.parametrize(
    "error", [TimeoutError(), RuntimeError("provider unavailable"), ValueError("parse failed")]
)
async def test_news_exception_cannot_interrupt_plan_or_refresh_it(strategy, error):
    state = CurrentPortfolioState(Decimal("100000"))
    plan = base_plan(
        state,
        PortfolioCandidate(
            "AAA", Signal.BUY, Decimal("100"), exit_context=strategy_context(strategy)
        ),
    )
    plan = replace(plan, decisions=(approved_test_boundary(plan.decisions[0]),))
    news = PersistedNews(error=error)
    result = await apply_portfolio_news_gate(
        plan=plan, state=state, portfolio_id=uuid4(), news=news, as_of=NOW
    )
    assert result.plan.decisions[0].is_approved_buy
    assert result.plan.decisions[0].news_coverage == "UNAVAILABLE"
    assert news.refreshes == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20,
        PortfolioDecisionReason.EMA20_ENTRY_REVALIDATION_UNAVAILABLE,
        PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS,
        PortfolioDecisionReason.MAX_POSITIONS,
        PortfolioDecisionReason.INSUFFICIENT_CASH,
    ],
)
async def test_ema_positive_news_never_overrides_real_hard_gate(reason):
    state = CurrentPortfolioState(Decimal("100000"))
    plan = base_plan(
        state,
        PortfolioCandidate(
            "AAA",
            Signal.BUY,
            Decimal("100"),
            pre_decision_reason=reason,
            exit_context=strategy_context(),
        ),
    )
    original = plan.decisions[0]
    result = await apply_portfolio_news_gate(
        plan=plan, state=state, portfolio_id=uuid4(), news=PersistedNews(), as_of=NOW
    )
    decision = result.plan.decisions[0]
    assert not decision.is_approved_buy
    assert decision.final_action is PortfolioFinalAction.NOT_ACTIONABLE
    assert decision.terminal_reason == original.terminal_reason


@pytest.mark.asyncio
async def test_ema_news_preserves_approved_manual_stop_buy():
    state = CurrentPortfolioState(Decimal("100000"))
    plan = base_plan(
        state,
        PortfolioCandidate("AAA", Signal.BUY, Decimal("100"), exit_context=strategy_context()),
    )
    result = await apply_portfolio_news_gate(
        plan=plan,
        state=state,
        portfolio_id=uuid4(),
        news=PersistedNews(NewsEffect.EXIT_REQUIRED),
        as_of=NOW,
    )
    decision = result.plan.decisions[0]
    assert decision.is_approved_buy
    assert decision.loss_control_source is LossControlSource.USER_MANUAL
    assert decision.manual_stop_required
    assert decision.loss_control_boundary_price is None


@pytest.mark.asyncio
async def test_ema_final_counts_ignore_news_and_keep_both_deterministic_blockers():
    state = CurrentPortfolioState(Decimal("100000"))
    plan = base_plan(
        state,
        *(
            PortfolioCandidate(
                ticker,
                Signal.BUY,
                Decimal("100"),
                exit_context=strategy_context(),
                pre_decision_reason=(
                    PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
                    if ticker == "D"
                    else PortfolioDecisionReason.MAX_POSITIONS
                    if ticker == "C"
                    else None
                ),
            )
            for ticker in ("A", "B", "C", "D")
        ),
    )
    plan = replace(
        plan,
        decisions=tuple(
            approved_test_boundary(d) if d.ticker in {"A", "B"} else d for d in plan.decisions
        ),
    )

    class DifferentNews(PersistedNews):
        async def assess(self, portfolio_id, ticker, *, as_of):
            self.effect = (
                NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE if ticker == "A" else NewsEffect.BUY_BLOCKED
            )
            return await super().assess(portfolio_id, ticker, as_of=as_of)

    result = await apply_portfolio_news_gate(
        plan=plan, state=state, portfolio_id=uuid4(), news=DifferentNews(), as_of=NOW
    )
    statuses = tuple(
        CandidateOrchestrationStatus(t, CandidateDataStatus.READY, DAY, Signal.BUY, "TEST")
        for t in ("A", "B", "C", "D")
    )
    readiness = PortfolioDecisionOrchestrator.final_readiness(statuses, result.plan)
    assert readiness.approved_buys == readiness.buy_funnel.final_approved_buys == 2
    assert readiness.buy_funnel.reached_news == 0
    assert readiness.buy_funnel.news_advisory_only
    assert [d.ticker for d in result.plan.decisions if d.is_approved_buy] == ["A", "B"]
    assert result.plan.decisions[2].terminal_reason is PortfolioDecisionReason.MAX_POSITIONS
    assert (
        result.plan.decisions[3].terminal_reason
        is PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", [StrategyName.EMA20_PULLBACK, StrategyName.MICHO_150])
@pytest.mark.parametrize("signal", [Signal.HOLD, Signal.SELL])
@pytest.mark.parametrize(
    "effect", [NewsEffect.NO_EFFECT, NewsEffect.EXIT_REQUIRED, NewsEffect.ATTENTION]
)
async def test_news_cannot_create_exit_or_override_technical_hold_sell(strategy, signal, effect):
    state = CurrentPortfolioState(
        Decimal("10000"), (PortfolioStatePosition("AAA", 10, Decimal("100")),)
    )
    plan = base_plan(
        state,
        PortfolioCandidate(
            "AAA",
            signal,
            Decimal("100"),
            exit_context=strategy_context(strategy, signal),
        ),
    )
    original = plan.decisions[0]
    result = await apply_portfolio_news_gate(
        plan=plan, state=state, portfolio_id=uuid4(), news=PersistedNews(effect), as_of=NOW
    )
    decision = result.plan.decisions[0]
    assert (
        decision.final_action,
        decision.decision,
        decision.reason,
        decision.is_final_actionable,
    ) == (
        original.final_action,
        original.decision,
        original.reason,
        original.is_final_actionable,
    )
    assert decision.news_advisory_only


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy", "profile_id"),
    [
        (StrategyName.EMA20_PULLBACK, "ema20-pullback-v1"),
        (StrategyName.MICHO_150, "micho-150-v1"),
    ],
)
@pytest.mark.parametrize("context_failure", [False, True])
async def test_real_plan_route_and_profile_work_with_all_news_providers_unconfigured(
    client,
    monkeypatch,
    strategy,
    profile_id,
    context_failure,
):
    from types import SimpleNamespace

    from alphapilot.api.routes import portfolio as routes
    from alphapilot.core.config import settings
    from alphapilot.main import app
    from alphapilot.news.service import NewsService
    from alphapilot.portfolio.orchestration import PortfolioOrchestrationResult

    for key in ("ADANOS_API_KEY", "FINNHUB_API_KEY", "NEWS_AI_CLASSIFIER_API_KEY"):
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "NEWS_AI_CLASSIFIER_ENABLED", False)
    monkeypatch.setattr(settings, "OLLAMA_NEWS_FALLBACK_ENABLED", False)
    state = CurrentPortfolioState(Decimal("100000"))
    plan = base_plan(
        state,
        *(
            PortfolioCandidate(
                t, Signal.BUY, Decimal("100"), exit_context=strategy_context(strategy)
            )
            for t in ("A", "B")
        ),
    )
    blocked = replace(
        plan.decisions[1],
        decision=PortfolioDecisionType.SKIP,
        reason=PortfolioDecisionReason.MAX_POSITIONS,
        terminal_reason=PortfolioDecisionReason.MAX_POSITIONS,
        execution_readiness=ExecutionReadiness.RESEARCH_ONLY,
        execution_readiness_reason=ExecutionReadinessReason.NOT_A_NEW_BUY,
        loss_control_policy="NONE",
        loss_control_boundary_price=None,
        loss_control_active=False,
        loss_control_trigger=None,
        final_action=PortfolioFinalAction.NOT_ACTIONABLE,
        is_final_actionable=False,
    )
    plan = replace(plan, decisions=(approved_test_boundary(plan.decisions[0]), blocked))
    statuses = tuple(
        CandidateOrchestrationStatus(t, CandidateDataStatus.READY, DAY, Signal.BUY, "TEST")
        for t in ("A", "B")
    )

    class Orchestrator:
        async def build_plan(self, **kwargs):
            assert kwargs["strategy_name"] is strategy
            assert kwargs["hybrid_trend_threshold_pct"] == Decimal("2")
            return PortfolioOrchestrationResult(
                plan,
                DAY,
                DAY,
                statuses,
                PortfolioDecisionOrchestrator.final_readiness(statuses, plan),
            )

    class Persistent:
        async def excluded_tickers(self, portfolio_id):
            return frozenset()

    async def persistent_state(*args):
        return state, SimpleNamespace(revision=7)

    async def forbidden_refresh(*args, **kwargs):
        pytest.fail("Plan attempted a News provider refresh")

    async def failed_context(*args, **kwargs):
        raise TimeoutError("controlled context failure")

    monkeypatch.setattr(routes, "_persistent_state", persistent_state)
    monkeypatch.setattr(NewsService, "refresh_portfolio", forbidden_refresh)
    if context_failure:
        monkeypatch.setattr(NewsService, "assess", failed_context)
    app.dependency_overrides[routes.get_portfolio_decision_orchestrator] = lambda: Orchestrator()
    app.dependency_overrides[routes.get_research_portfolio_service] = lambda: Persistent()
    try:
        profiles = await client.get("/api/v1/portfolio/strategy-profiles")
        response = await client.post(
            "/api/v1/portfolio/plan",
            json={
                "strategy": strategy.value,
                "portfolio_id": str(uuid4()),
                "as_of_date": DAY.isoformat(),
                "tickers": ["A", "B"],
            },
        )
    finally:
        app.dependency_overrides.pop(routes.get_portfolio_decision_orchestrator, None)
        app.dependency_overrides.pop(routes.get_research_portfolio_service, None)
    assert profiles.status_code == response.status_code == 200
    body = response.json()
    assert body["strategy_profile"]["profile_id"] == profile_id
    assert body["readiness"]["final_approved_buys"] == body["readiness"]["approved_buys"] == 1
    assert body["decisions"][0]["final_action"] == "BUY"
    assert body["decisions"][0]["news_advisory_only"] is True
    assert body["decisions"][1]["terminal_reason"] == "MAX_POSITIONS"
    assert body["news_enrichment"]["aggregate_api_calls"] == 0
    assert body["news_enrichment"]["attributable_api_calls"] == 0
    assert body["news_enrichment"]["candidate_shortlist"] == []
    assert body["news_enrichment"]["assessed_buy_tickers"] == ["A"]
