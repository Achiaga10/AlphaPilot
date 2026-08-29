from datetime import date
from decimal import Decimal

import pytest

from alphapilot.portfolio.actions import (
    ManualPortfolioSellService,
    ManualSellPriceSource,
    ManualSellReason,
    PlanActionApplyReason,
    PlanActionQuantitySemantics,
    PlanActionValidationStatus,
    PortfolioPlanActionService,
)
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecision,
    PortfolioDecisionEngine,
    PortfolioStatePosition,
)
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.strategy.signal import Signal


def _buy_plan() -> tuple[PortfolioDecision, PortfolioDecision]:
    plan = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(cash=Decimal("100000")),
        (
            PortfolioCandidate("AAA", Signal.BUY, Decimal("100"), Decimal("2"), Decimal("4")),
            PortfolioCandidate("BBB", Signal.BUY, Decimal("100"), Decimal("1"), Decimal("4")),
        ),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    return plan.decisions[0], plan.decisions[1]


def test_rank_is_advisory_and_each_action_revalidates_current_draft() -> None:
    first, second = _buy_plan()
    service = PortfolioPlanActionService()
    initial = CurrentPortfolioState(cash=Decimal("100000"))

    second_first = service.apply(
        state=initial,
        decision=second,
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert second.depends_on_action_ids == ()
    assert second_first.applied is True
    assert second_first.portfolio.positions[0].ticker == "BBB"

    applied_first = service.apply(
        state=initial,
        decision=first,
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert applied_first.applied is True
    assert applied_first.cash_after == Decimal("90000")
    assert applied_first.portfolio.positions[0].ticker == "AAA"
    assert first.action_id is not None

    duplicate = service.apply(
        state=applied_first.portfolio,
        decision=first,
        applied_action_ids=frozenset({first.action_id}),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert duplicate.reason == PlanActionApplyReason.ALREADY_APPLIED

    applied_second = service.apply(
        state=applied_first.portfolio,
        decision=second,
        applied_action_ids=frozenset({first.action_id}),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert applied_second.applied is True
    assert applied_second.cash_after == Decimal("80000")
    assert [item.ticker for item in applied_second.portfolio.positions] == ["AAA", "BBB"]

    cash_blocked = service.apply(
        state=CurrentPortfolioState(cash=Decimal("1")),
        decision=first,
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert cash_blocked.reason == PlanActionApplyReason.INSUFFICIENT_CURRENT_DRAFT_CASH
    assert cash_blocked.cash_after == Decimal("1")


def test_buy_preview_recalculates_user_quantity_and_enforces_hard_caps() -> None:
    first, _ = _buy_plan()
    service = PortfolioPlanActionService()
    state = CurrentPortfolioState(cash=Decimal("100000"))

    preview = service.apply(
        state=state,
        decision=first,
        applied_action_ids=frozenset(),
        requested_shares=50,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        apply=False,
    )
    assert preview.applied is False
    assert preview.reason == PlanActionApplyReason.READY
    assert preview.validation_status == PlanActionValidationStatus.VALID
    assert preview.quantity_semantics == PlanActionQuantitySemantics.USER_QUANTITY_OVERRIDE
    assert preview.recommended_shares == 100
    assert preview.requested_shares == 50
    assert preview.requested_allocation_dollars == Decimal("5000")
    assert preview.cash_after == Decimal("95000")
    assert preview.resulting_position_weight_pct == Decimal("5.00")
    assert preview.modeled_position_risk_dollars is None
    assert preview.portfolio == state

    rejected = service.apply(
        state=state,
        decision=first,
        applied_action_ids=frozenset(),
        requested_shares=101,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        apply=False,
    )
    assert rejected.validation_status == PlanActionValidationStatus.REJECTED
    assert rejected.reason == PlanActionApplyReason.MAX_POSITION_WEIGHT


def test_same_plan_candidate_gets_current_quantity_and_constraint_revalidation() -> None:
    first, _ = _buy_plan()
    held = PortfolioStatePosition(
        "HELD",
        250,
        Decimal("100"),
        sector=first.sector,
    )
    state = CurrentPortfolioState(cash=Decimal("75000"), positions=(held,))
    service = PortfolioPlanActionService()

    current = service.apply(
        state=state,
        decision=first,
        applied_action_ids=frozenset(),
        requested_shares=None,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        apply=False,
    )
    assert current.validation_status == PlanActionValidationStatus.VALID
    assert current.quantity_semantics == (
        PlanActionQuantitySemantics.CURRENT_REVALIDATED_RECOMMENDATION
    )
    assert current.recommended_shares == 50
    assert current.requested_shares == 50

    stale_original_quantity = service.apply(
        state=state,
        decision=first,
        applied_action_ids=frozenset(),
        requested_shares=100,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        apply=False,
    )
    assert stale_original_quantity.validation_status == PlanActionValidationStatus.REJECTED
    assert stale_original_quantity.reason == PlanActionApplyReason.SECTOR_LIMIT

    already_held = service.apply(
        state=CurrentPortfolioState(
            cash=Decimal("90000"),
            positions=(PortfolioStatePosition("AAA", 100, Decimal("100")),),
        ),
        decision=first,
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert already_held.reason == PlanActionApplyReason.POSITION_ALREADY_HELD

    max_positions = service.apply(
        state=CurrentPortfolioState(
            cash=Decimal("10000"),
            positions=tuple(PortfolioStatePosition(f"P{i}", 1, Decimal("9000")) for i in range(10)),
        ),
        decision=first,
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
    )
    assert max_positions.reason == PlanActionApplyReason.MAX_POSITIONS


def test_approved_sell_applies_full_position_after_dependencies() -> None:
    held = PortfolioStatePosition("EXIT", 10, Decimal("50"), cost_basis=Decimal("40"))
    plan = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(cash=Decimal("1000"), positions=(held,)),
        (PortfolioCandidate("EXIT", Signal.SELL, Decimal("50")),),
    )
    result = PortfolioPlanActionService().apply(
        state=CurrentPortfolioState(cash=Decimal("1000"), positions=(held,)),
        decision=plan.decisions[0],
        applied_action_ids=frozenset(),
    )
    assert result.applied is True
    assert result.cash_after == Decimal("1500")
    assert result.portfolio.positions == ()


class _Prices:
    def __init__(self, value: tuple[Decimal, date] | None) -> None:
        self.value = value

    async def get_latest_stored_price(self, ticker: str) -> tuple[Decimal, date] | None:
        assert ticker == "AAA"
        return self.value


@pytest.mark.asyncio
async def test_manual_sell_preview_partial_full_override_and_missing_price() -> None:
    held = PortfolioStatePosition(
        "AAA", 100, Decimal("90"), cost_basis=Decimal("70"), modeled_risk_dollars=Decimal("500")
    )
    state = CurrentPortfolioState(cash=Decimal("1000"), positions=(held,))
    service = ManualPortfolioSellService(_Prices((Decimal("105"), date(2026, 8, 25))))

    preview = await service.sell(
        state=state,
        ticker="aaa",
        shares_to_sell=40,
        execution_price=None,
        apply=False,
    )
    assert preview.reason == ManualSellReason.READY
    assert preview.price_source == ManualSellPriceSource.LATEST_STORED_CANDLE
    assert preview.price_date == date(2026, 8, 25)
    assert preview.gross_proceeds == Decimal("4200")
    assert preview.cash_after == Decimal("5200")
    assert preview.shares_remaining == 60
    assert preview.portfolio.positions[0].cost_basis == Decimal("70")
    assert preview.portfolio.positions[0].modeled_risk_dollars == Decimal("300")

    full = await service.sell(
        state=state,
        ticker="AAA",
        shares_to_sell=100,
        execution_price=Decimal("106"),
        apply=True,
    )
    assert full.reason == ManualSellReason.APPLIED
    assert full.price_source == ManualSellPriceSource.USER_PROVIDED
    assert full.price_date is None
    assert full.cash_after == Decimal("11600")
    assert full.position_removed is True
    assert full.portfolio.positions == ()

    missing = await ManualPortfolioSellService(_Prices(None)).sell(
        state=state,
        ticker="AAA",
        shares_to_sell=1,
        execution_price=None,
        apply=True,
    )
    assert missing.reason == ManualSellReason.STORED_PRICE_UNAVAILABLE
    assert missing.applied is False

    invalid = await service.sell(
        state=state,
        ticker="AAA",
        shares_to_sell=101,
        execution_price=None,
        apply=True,
    )
    assert invalid.reason == ManualSellReason.INVALID_SHARE_QUANTITY
