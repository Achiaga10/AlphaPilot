from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from alphapilot.copilot.direct_answer import render_direct_answer
from alphapilot.copilot.intent import CopilotIntent, classify_question
from alphapilot.portfolio.actions import PlanActionApplyReason, PortfolioPlanActionService
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
)
from alphapilot.portfolio.entry_safety import (
    Ema20EntryPriceSource,
    Ema20EntryRelation,
    Ema20EntrySafetyReason,
    Ema20EntrySafetyStatus,
    assess_ema20_entry_safety,
)
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.strategy.signal import Signal

NOW = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
EMA_DAY = date(2026, 8, 27)


def assess(price: Decimal | None, ema20: Decimal | None = Decimal("100")):
    return assess_ema20_entry_safety(
        ticker="TEST",
        as_of=NOW,
        entry_price=price,
        entry_price_source=(
            Ema20EntryPriceSource.ALPACA_LIVE_SNAPSHOT if price is not None else None
        ),
        entry_price_timestamp=NOW if price is not None else None,
        ema20=ema20,
        ema20_as_of=EMA_DAY if ema20 is not None else None,
    )


@pytest.mark.parametrize(
    ("price", "relation", "status"),
    [
        (Decimal("99"), Ema20EntryRelation.BELOW, Ema20EntrySafetyStatus.ELIGIBLE),
        (Decimal("100"), Ema20EntryRelation.TOUCHING_OR_NEAR, Ema20EntrySafetyStatus.ELIGIBLE),
        (Decimal("100.5"), Ema20EntryRelation.TOUCHING_OR_NEAR, Ema20EntrySafetyStatus.ELIGIBLE),
        (Decimal("101"), Ema20EntryRelation.TOUCHING_OR_NEAR, Ema20EntrySafetyStatus.ELIGIBLE),
        (Decimal("101.01"), Ema20EntryRelation.EXTENDED_ABOVE, Ema20EntrySafetyStatus.BLOCKED),
        (Decimal("115"), Ema20EntryRelation.EXTENDED_ABOVE, Ema20EntrySafetyStatus.BLOCKED),
    ],
)
def test_predeclared_existing_one_percent_boundary(price, relation, status) -> None:
    result = assess(price)
    assert result.relation is relation
    assert result.status is status


def test_missing_price_or_ema_fails_closed() -> None:
    assert assess(None).reason is Ema20EntrySafetyReason.EMA20_ENTRY_REVALIDATION_UNAVAILABLE
    assert assess(Decimal("100"), None).status is Ema20EntrySafetyStatus.UNAVAILABLE


def test_stale_live_quote_fails_closed() -> None:
    result = assess_ema20_entry_safety(
        ticker="TEST",
        as_of=NOW,
        entry_price=Decimal("100"),
        entry_price_source=Ema20EntryPriceSource.ALPACA_LIVE_SNAPSHOT,
        entry_price_timestamp=NOW,
        ema20=Decimal("100"),
        ema20_as_of=EMA_DAY,
        entry_price_is_fresh=False,
    )
    assert result.status is Ema20EntrySafetyStatus.UNAVAILABLE


def test_current_movement_is_revalidated_in_both_directions() -> None:
    valid_signal = assess(Decimal("100.5"))
    rallied = assess(Decimal("110"))
    returned = assess(Decimal("100.5"))
    assert valid_signal.status is Ema20EntrySafetyStatus.ELIGIBLE
    assert rallied.reason is Ema20EntrySafetyReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
    assert returned.status is Ema20EntrySafetyStatus.ELIGIBLE


def test_axon_incident_shaped_control_is_blocked() -> None:
    result = assess_ema20_entry_safety(
        ticker="AXON",
        as_of=NOW,
        entry_price=Decimal("609.00"),
        entry_price_source=Ema20EntryPriceSource.ALPACA_LIVE_SNAPSHOT,
        entry_price_timestamp=NOW,
        ema20=Decimal("597.1382581750427727951172336"),
        ema20_as_of=EMA_DAY,
    )
    assert result.distance_to_ema20_pct == pytest.approx(Decimal("1.9864"), abs=Decimal("0.0001"))
    assert result.reason is Ema20EntrySafetyReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20


def test_fast_incident_shaped_positive_control_is_eligible() -> None:
    result = assess_ema20_entry_safety(
        ticker="FAST",
        as_of=NOW,
        entry_price=Decimal("50.28"),
        entry_price_source=Ema20EntryPriceSource.ALPACA_LIVE_SNAPSHOT,
        entry_price_timestamp=NOW,
        ema20=Decimal("50.44696835243861901010882936"),
        ema20_as_of=EMA_DAY,
    )
    assert result.relation is Ema20EntryRelation.BELOW
    assert result.status is Ema20EntrySafetyStatus.ELIGIBLE


def test_action_revalidation_cannot_be_overridden_by_news_or_rank() -> None:
    state = CurrentPortfolioState(cash=Decimal("100000"))
    decision = (
        PortfolioDecisionEngine()
        .build_plan(
            state,
            (PortfolioCandidate("AXON", Signal.BUY, Decimal("100"), Decimal("999")),),
            sizing_policy=SizingPolicyName.EQUAL_SLOT,
        )
        .decisions[0]
    )
    blocked = replace(
        decision,
        entry_safety=assess(Decimal("110")),
        news_effect="POSITIVE_CONTEXT",
    )
    result = PortfolioPlanActionService().apply(
        state=state,
        decision=blocked,
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        require_ema20_entry_safety=True,
        now=NOW,
    )
    assert result.reason is PlanActionApplyReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
    assert result.applied is False


def test_action_revalidation_rejects_stale_live_assessment() -> None:
    state = CurrentPortfolioState(cash=Decimal("100000"))
    decision = (
        PortfolioDecisionEngine()
        .build_plan(
            state,
            (PortfolioCandidate("AAA", Signal.BUY, Decimal("100")),),
            sizing_policy=SizingPolicyName.EQUAL_SLOT,
        )
        .decisions[0]
    )
    old = NOW - timedelta(minutes=3)
    assessment = assess_ema20_entry_safety(
        ticker="AAA",
        as_of=old,
        entry_price=Decimal("100"),
        entry_price_source=Ema20EntryPriceSource.ALPACA_LIVE_SNAPSHOT,
        entry_price_timestamp=old,
        ema20=Decimal("100"),
        ema20_as_of=EMA_DAY,
    )
    result = PortfolioPlanActionService().apply(
        state=state,
        decision=replace(decision, entry_safety=assessment),
        applied_action_ids=frozenset(),
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        require_ema20_entry_safety=True,
        now=NOW,
    )
    assert result.reason is PlanActionApplyReason.EMA20_ENTRY_REVALIDATION_UNAVAILABLE


def test_copilot_entry_safety_questions_are_deterministic() -> None:
    question = "Is AXON too extended to buy?"
    assert classify_question(question) is CopilotIntent.EMA20_ENTRY_SAFETY
    facts = {
        "position.ticker": {"value": "AXON"},
        "query.question": {"value": question},
        "entry_safety.status": {"value": "BLOCKED"},
        "entry_safety.reason": {"value": "ENTRY_TOO_EXTENDED_ABOVE_EMA20"},
        "entry_safety.entry_price": {"value": "609"},
        "entry_safety.ema20": {"value": "597.138258175"},
        "entry_safety.distance_pct": {"value": "1.9864"},
        "entry_safety.relation": {"value": "EXTENDED_ABOVE"},
        "entry_safety.price_source": {"value": "ALPACA_LIVE_SNAPSHOT"},
        "entry_safety.price_timestamp": {"value": "2026-08-28T05:13:00Z"},
    }
    answer = render_direct_answer(CopilotIntent.EMA20_ENTRY_SAFETY, facts)
    assert "BLOCKED" in answer.answer
    assert "+1.99%" in answer.answer

    override_question = "Did positive News override the EMA entry rule?"
    assert classify_question(override_question) is CopilotIntent.EMA20_ENTRY_SAFETY
    facts["query.question"] = {"value": override_question}
    override = render_direct_answer(CopilotIntent.EMA20_ENTRY_SAFETY, facts)
    assert override.answer == "No. Positive News cannot override the EMA20 entry-safety rule."
