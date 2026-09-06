from dataclasses import replace
from datetime import date
from decimal import Decimal

from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
    PortfolioFinalAction,
)
from alphapilot.portfolio.execution_readiness import ExecutionReadiness
from alphapilot.portfolio.orchestration import (
    BuyFunnelStage,
    CandidateDataStatus,
    CandidateOrchestrationStatus,
    PlanReadinessStatus,
    PortfolioDecisionOrchestrator,
)
from alphapilot.portfolio.sizing import (
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingPolicyName,
)
from alphapilot.strategy.signal import Signal


def _status(ticker: str = "UBER") -> CandidateOrchestrationStatus:
    return CandidateOrchestrationStatus(
        ticker=ticker,
        status=CandidateDataStatus.READY,
        data_as_of_date=date(2026, 9, 2),
        signal=Signal.BUY,
        reason="EMA20_PULLBACK_RECLAIM",
    )


def test_final_approved_counts_only_final_actionable_rows() -> None:
    base = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(Decimal("100000")),
        (
            PortfolioCandidate("ACTION", Signal.BUY, Decimal("100"), Decimal("2")),
            PortfolioCandidate("BLOCK", Signal.BUY, Decimal("100"), Decimal("1")),
        ),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    actionable, blocked = base.decisions
    actionable = replace(
        actionable,
        reason=PortfolioDecisionReason.BUY_APPROVED,
        execution_readiness=ExecutionReadiness.ACTIONABLE,
        loss_control_active=True,
        final_action=PortfolioFinalAction.BUY,
        terminal_reason=PortfolioDecisionReason.BUY_APPROVED,
        is_final_actionable=True,
    )
    blocked = replace(
        blocked,
        decision=PortfolioDecisionType.SKIP,
        reason=PortfolioDecisionReason.NEWS_RISK_BLOCK,
        terminal_reason=PortfolioDecisionReason.NEWS_RISK_BLOCK,
        final_action=PortfolioFinalAction.NOT_ACTIONABLE,
        loss_control_active=True,
        is_final_actionable=False,
    )
    plan = replace(base, decisions=(actionable, blocked))
    readiness = PortfolioDecisionOrchestrator.final_readiness(
        (_status("ACTION"), _status("BLOCK")), plan
    )

    assert readiness.technical_buy_signals == 2
    assert readiness.final_approved_buys == 1
    assert readiness.approved_buys == 1
    assert readiness.final_approved_buys == sum(
        item.final_action is PortfolioFinalAction.BUY and item.is_final_actionable
        for item in plan.decisions
    )
    assert readiness.buy_rejections_by_reason == {"NEWS_RISK_BLOCK": 1}
    groups = {group.stage: group.count for group in readiness.buy_funnel.groups}
    assert groups == {
        BuyFunnelStage.FINAL_APPROVED_BUY: 1,
        BuyFunnelStage.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE: 1,
    }
    assert sum(groups.values()) == readiness.technical_buy_signals


def test_allocation_buy_without_loss_control_has_one_terminal_non_actionable_state() -> None:
    plan = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(Decimal("100000")),
        (PortfolioCandidate("IBKR", Signal.BUY, Decimal("92.96"), Decimal("1")),),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    decision = plan.decisions[0]
    readiness = PortfolioDecisionOrchestrator.final_readiness((_status("IBKR"),), plan)

    assert decision.decision is PortfolioDecisionType.BUY
    assert decision.allocation_reason is PortfolioDecisionReason.BUY_APPROVED
    assert decision.reason is PortfolioDecisionReason.LOSS_CONTROL_UNAVAILABLE
    assert decision.terminal_reason is PortfolioDecisionReason.LOSS_CONTROL_UNAVAILABLE
    assert decision.final_action is PortfolioFinalAction.NOT_ACTIONABLE
    assert decision.is_final_actionable is False
    assert decision.target_allocation_dollars > 0
    assert readiness.final_approved_buys == 0
    assert readiness.approved_buys == 0
    assert readiness.buy_rejections_by_reason == {"LOSS_CONTROL_UNAVAILABLE": 1}
    assert readiness.buy_funnel.groups[0].stage is BuyFunnelStage.LOSS_CONTROL_UNAVAILABLE


def test_entry_safety_and_user_exclusion_never_increment_approved_buy_count() -> None:
    plan = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(Decimal("100000")),
        (
            PortfolioCandidate(
                "EMA",
                Signal.BUY,
                Decimal("100"),
                Decimal("2"),
                pre_decision_reason=PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20,
            ),
            PortfolioCandidate(
                "UBER",
                Signal.BUY,
                Decimal("100"),
                Decimal("999"),
                pre_decision_reason=(PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS),
            ),
        ),
    )
    readiness = PortfolioDecisionOrchestrator.final_readiness(
        (_status("EMA"), _status("UBER")), plan
    )

    assert readiness.final_approved_buys == 0
    assert readiness.user_excluded_buys == 1
    assert plan.decisions[0].target_allocation_dollars == 0
    assert plan.decisions[1].target_allocation_dollars == 0
    assert readiness.status == PlanReadinessStatus.NO_ACTION


def test_restore_to_pool_reenables_normal_policy_without_forcing_buy() -> None:
    state = CurrentPortfolioState(Decimal("100000"))
    excluded = PortfolioDecisionEngine().build_plan(
        state,
        (
            PortfolioCandidate(
                "UBER",
                Signal.BUY,
                Decimal("100"),
                Decimal("1"),
                pre_decision_reason=(PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS),
            ),
        ),
    )
    restored = PortfolioDecisionEngine().build_plan(
        state,
        (PortfolioCandidate("UBER", Signal.BUY, Decimal("100"), Decimal("1")),),
    )

    assert excluded.decisions[0].decision == PortfolioDecisionType.SKIP
    assert restored.decisions[0].reason != (
        PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS
    )
    assert restored.decisions[0].decision in {
        PortfolioDecisionType.BUY,
        PortfolioDecisionType.SKIP,
    }
