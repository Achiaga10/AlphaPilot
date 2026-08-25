from decimal import Decimal

from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
    PortfolioStatePosition,
)
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import (
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingPolicyName,
)
from alphapilot.strategy.signal import Signal


def test_plan_respects_sell_ranking_held_sector_and_risk_constraints() -> None:
    state = CurrentPortfolioState(
        cash=Decimal("30000"),
        positions=(
            PortfolioStatePosition(
                "AAA",
                300,
                Decimal("100"),
                sector="Technology",
                modeled_risk_dollars=Decimal("3000"),
            ),
            PortfolioStatePosition(
                "SELL",
                400,
                Decimal("100"),
                sector="Health Care",
                modeled_risk_dollars=Decimal("4000"),
            ),
        ),
    )
    candidates = (
        PortfolioCandidate(
            "TECH", Signal.BUY, Decimal("100"), Decimal("0.9"), Decimal("5"), "Technology"
        ),
        PortfolioCandidate(
            "NEW", Signal.BUY, Decimal("100"), Decimal("0.8"), Decimal("5"), "Industrials"
        ),
        PortfolioCandidate(
            "AAA", Signal.BUY, Decimal("100"), Decimal("1"), Decimal("5"), "Technology"
        ),
        PortfolioCandidate("SELL", Signal.SELL, Decimal("100"), sector="Health Care"),
    )
    plan = PortfolioDecisionEngine().build_plan(state, candidates, PortfolioRiskConfig())
    decisions = {item.ticker: item for item in plan.decisions}

    assert decisions["SELL"].decision == PortfolioDecisionType.SELL
    assert decisions["SELL"].reason == PortfolioDecisionReason.SELL_APPROVED
    assert decisions["AAA"].reason == PortfolioDecisionReason.ALREADY_HELD
    assert decisions["TECH"].reason == PortfolioDecisionReason.SECTOR_LIMIT
    assert decisions["NEW"].decision == PortfolioDecisionType.BUY
    assert decisions["NEW"].proposed_shares == 100
    assert plan.equity == Decimal("100000")
    assert plan.current_portfolio_risk == Decimal("7000")
    assert plan.available_portfolio_risk == Decimal("1000")


def test_missing_sector_is_unclassified_and_output_is_deterministic() -> None:
    state = CurrentPortfolioState(cash=Decimal("100000"))
    candidates = (
        PortfolioCandidate("XYZ", Signal.BUY, Decimal("100"), Decimal("0.1"), Decimal("5"), None),
    )
    engine = PortfolioDecisionEngine()
    first = engine.build_plan(state, candidates)
    second = engine.build_plan(state, candidates)
    assert first == second
    assert first.decisions[0].sector == "Unclassified"


def test_max_positions_and_flat_sell_have_stable_reasons() -> None:
    positions = tuple(PortfolioStatePosition(str(index), 1, Decimal("100")) for index in range(10))
    plan = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(cash=Decimal("10000"), positions=positions),
        (
            PortfolioCandidate("BUY", Signal.BUY, Decimal("100"), atr=Decimal("5")),
            PortfolioCandidate("FLAT", Signal.SELL, Decimal("100")),
        ),
    )
    reasons = {item.ticker: item.reason for item in plan.decisions}
    assert reasons == {
        "BUY": PortfolioDecisionReason.MAX_POSITIONS,
        "FLAT": PortfolioDecisionReason.NO_POSITION_TO_SELL,
    }


def test_volatility_normalized_plan_allocates_candidate_group() -> None:
    candidates = (
        PortfolioCandidate("LOW", Signal.BUY, Decimal("100"), Decimal("2"), Decimal("2"), "A"),
        PortfolioCandidate("HIGH", Signal.BUY, Decimal("100"), Decimal("1"), Decimal("4"), "B"),
    )
    plan = PortfolioDecisionEngine().build_plan(
        CurrentPortfolioState(cash=Decimal("100000")),
        candidates,
        sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
    )
    assert [item.ticker for item in plan.decisions] == ["LOW", "HIGH"]
    assert all(item.decision == PortfolioDecisionType.BUY for item in plan.decisions)
    assert all(item.target_weight_pct <= Decimal("10") for item in plan.decisions)
