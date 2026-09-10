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
)
from alphapilot.portfolio.entry_safety import (
    Ema20EntryPriceSource,
    assess_ema20_entry_safety,
)
from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
    LossControlEvidence,
    LossControlSource,
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

DAY = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 22, tzinfo=UTC)


def _context(strategy: StrategyName = StrategyName.EMA20_PULLBACK) -> StrategyExitContext:
    micho = strategy is StrategyName.MICHO_150
    return StrategyExitContext(
        strategy=strategy,
        data_as_of_date=DAY,
        reference_close=Decimal("100"),
        current_signal=Signal.BUY,
        signal_reason="CONTROLLED_BUY",
        exit_mode="close-below-sma150" if micho else "hybrid-2%",
        current_exit_state=(
            StrategyExitState.ABOVE_SMA150 if micho else StrategyExitState.ABOVE_EMA20
        ),
        ema20=None if micho else Decimal("100"),
        ema50=None if micho else Decimal("95"),
        sma150=Decimal("90") if micho else None,
    )


def _entry_safety(ticker: str, entry_price: Decimal):
    return assess_ema20_entry_safety(
        ticker=ticker,
        as_of=NOW,
        entry_price=entry_price,
        entry_price_source=Ema20EntryPriceSource.COMPLETED_SESSION_CLOSE,
        entry_price_timestamp=NOW,
        ema20=Decimal("100"),
        ema20_as_of=DAY,
    )


def _system_evidence() -> LossControlEvidence:
    return LossControlEvidence(
        policy_name="CONTROLLED_APPROVED_SYSTEM_POLICY",
        boundary_price=Decimal("95"),
        distance_dollars=Decimal("5"),
        distance_pct=Decimal("5"),
        trigger="CONTROLLED_AUTOMATIC_STOP",
        strategy_profile_id="ema20-pullback-v1",
        strategy_profile_version=1,
        classification="APPROVED_SYSTEM_POLICY",
    )


def _ema_plan(*candidates: PortfolioCandidate):
    return PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(Decimal("100000")),
        candidates,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        strategy_name=StrategyName.EMA20_PULLBACK,
    )


def test_ema_manual_stop_policy_controlled_a_through_d_integration() -> None:
    plan = _ema_plan(
        PortfolioCandidate(
            "A",
            Signal.BUY,
            Decimal("100"),
            exit_context=_context(),
            entry_safety=_entry_safety("A", Decimal("100")),
        ),
        PortfolioCandidate(
            "B",
            Signal.BUY,
            Decimal("100"),
            exit_context=_context(),
            entry_safety=_entry_safety("B", Decimal("100")),
            approved_loss_control_evidence=_system_evidence(),
        ),
        PortfolioCandidate(
            "C",
            Signal.BUY,
            Decimal("102"),
            pre_decision_reason=PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20,
            exit_context=_context(),
            entry_safety=_entry_safety("C", Decimal("102")),
        ),
        PortfolioCandidate(
            "D",
            Signal.BUY,
            Decimal("100"),
            pre_decision_reason=PortfolioDecisionReason.MAX_POSITIONS,
            exit_context=_context(),
            entry_safety=_entry_safety("D", Decimal("100")),
        ),
    )
    decisions = {item.ticker: item for item in plan.decisions}

    manual = decisions["A"]
    assert manual.is_approved_buy
    assert manual.final_action is PortfolioFinalAction.BUY
    assert manual.execution_readiness is ExecutionReadiness.ACTIONABLE
    assert manual.execution_readiness_reason is ExecutionReadinessReason.MANUAL_STOP_REQUIRED
    assert manual.loss_control_source is LossControlSource.USER_MANUAL
    assert manual.manual_stop_required
    assert manual.loss_control_boundary_price is None
    assert manual.approved_protective_stop_price is None
    assert not manual.loss_control_active

    system = decisions["B"]
    assert system.is_approved_buy
    assert system.loss_control_source is LossControlSource.APPROVED_SYSTEM_POLICY
    assert not system.manual_stop_required
    assert system.loss_control_boundary_price == Decimal("95")
    assert system.approved_protective_stop_price == Decimal("95")
    assert system.loss_control_active

    assert decisions["C"].final_action is PortfolioFinalAction.NOT_ACTIONABLE
    assert decisions["C"].terminal_reason is PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
    assert decisions["D"].final_action is PortfolioFinalAction.NOT_ACTIONABLE
    assert decisions["D"].terminal_reason is PortfolioDecisionReason.MAX_POSITIONS
    assert not decisions["C"].manual_stop_required
    assert not decisions["D"].manual_stop_required

    statuses = tuple(
        CandidateOrchestrationStatus(
            ticker,
            CandidateDataStatus.READY,
            DAY,
            Signal.BUY,
            "CONTROLLED_BUY",
        )
        for ticker in ("A", "B", "C", "D")
    )
    readiness = PortfolioDecisionOrchestrator.final_readiness(statuses, plan)
    assert readiness.approved_buys == readiness.final_approved_buys == 2
    assert readiness.buy_funnel.final_approved_buys == 2
    groups = {group.stage: group.tickers for group in readiness.buy_funnel.groups}
    assert groups[BuyFunnelStage.FINAL_APPROVED_BUY] == ("A", "B")
    assert groups[BuyFunnelStage.EMA20_ENTRY_SAFETY_BLOCKED] == ("C",)
    assert groups[BuyFunnelStage.PORTFOLIO_POSITION_CONSTRAINT] == ("D",)


def test_ema_user_exclusion_still_blocks_before_manual_stop_policy() -> None:
    decision = _ema_plan(
        PortfolioCandidate(
            "EXCLUDED",
            Signal.BUY,
            Decimal("100"),
            pre_decision_reason=PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS,
            exit_context=_context(),
            entry_safety=_entry_safety("EXCLUDED", Decimal("100")),
        )
    ).decisions[0]
    assert decision.decision is PortfolioDecisionType.SKIP
    assert decision.terminal_reason is PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS
    assert not decision.is_approved_buy
    assert not decision.manual_stop_required
    assert decision.loss_control_source is LossControlSource.NONE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "effect",
    [
        NewsEffect.NO_EFFECT,
        NewsEffect.BUY_BLOCKED,
        NewsEffect.EXIT_REQUIRED,
        NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
    ],
)
@pytest.mark.parametrize("fail", [False, True])
async def test_ema_news_outcomes_and_failures_preserve_manual_stop_approval(effect, fail) -> None:
    class News:
        async def refresh_portfolio(self, *args, **kwargs):
            raise AssertionError("Advisory News must not refresh to establish approval")

        async def assess(self, portfolio_id, ticker, *, as_of):
            if fail:
                raise TimeoutError("controlled timeout")
            return NewsRiskAssessment(
                ticker=ticker,
                as_of=as_of,
                effect=effect,
                coverage=(
                    NewsCoverage.UNAVAILABLE
                    if effect is NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE
                    else NewsCoverage.CURRENT
                ),
                reason="Controlled advisory outcome",
            )

    state = CurrentPortfolioState(Decimal("100000"))
    plan = PortfolioDecisionEngine().build_plan(
        state,
        (
            PortfolioCandidate(
                "A",
                Signal.BUY,
                Decimal("100"),
                exit_context=_context(),
                entry_safety=_entry_safety("A", Decimal("100")),
            ),
        ),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        strategy_name=StrategyName.EMA20_PULLBACK,
    )
    result = await apply_portfolio_news_gate(
        plan=plan,
        state=state,
        portfolio_id=uuid4(),
        news=News(),
        as_of=NOW,
        strategy_name=StrategyName.EMA20_PULLBACK,
    )
    decision = result.plan.decisions[0]
    assert decision.is_approved_buy
    assert decision.final_action is PortfolioFinalAction.BUY
    assert decision.manual_stop_required
    assert decision.loss_control_source is LossControlSource.USER_MANUAL
    assert decision.news_advisory_only
    assert decision.news_coverage == ("UNAVAILABLE" if fail else effect_coverage(effect))


def effect_coverage(effect: NewsEffect) -> str:
    return (
        NewsCoverage.UNAVAILABLE.value
        if effect is NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE
        else NewsCoverage.CURRENT.value
    )


def test_micho_loss_control_behavior_is_unchanged() -> None:
    decision = (
        PortfolioDecisionEngine()
        .build_plan(
            CurrentPortfolioState(Decimal("100000")),
            (
                PortfolioCandidate(
                    "MCHO",
                    Signal.BUY,
                    Decimal("100"),
                    exit_context=_context(StrategyName.MICHO_150),
                ),
            ),
            sizing_policy=SizingPolicyName.EQUAL_SLOT,
            strategy_name=StrategyName.MICHO_150,
        )
        .decisions[0]
    )
    assert decision.is_approved_buy
    assert decision.execution_readiness_reason is ExecutionReadinessReason.LOSS_CONTROL_READY
    assert decision.loss_control_source is LossControlSource.APPROVED_SYSTEM_POLICY
    assert not decision.manual_stop_required
    assert decision.loss_control_boundary_price == Decimal("90")
    assert decision.approved_protective_stop_price is None
