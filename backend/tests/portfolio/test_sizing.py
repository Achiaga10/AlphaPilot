from decimal import Decimal

from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import (
    AtrRiskPositionSizer,
    AtrVolatilityNormalizedPositionSizer,
    PortfolioDecisionReason,
    SizingContext,
    VolatilityBatchContext,
    VolatilitySizingCandidate,
)


def context(**changes: Decimal | None) -> SizingContext:
    values = {
        "equity": Decimal("100000"),
        "cash": Decimal("50000"),
        "execution_price": Decimal("100"),
        "atr": Decimal("5"),
        "current_portfolio_risk": Decimal("0"),
        "sector_market_value": Decimal("0"),
    }
    values.update(changes)
    return SizingContext(**values)  # type: ignore[arg-type]


def test_one_percent_two_atr_risk_sizing_and_whole_share_floor() -> None:
    result = AtrRiskPositionSizer().size(context(atr=Decimal("6")), PortfolioRiskConfig())
    assert result.risk_budget == Decimal("1000")
    assert result.stop_distance == Decimal("12")
    assert result.shares == 83
    assert result.modeled_risk == Decimal("996")
    assert result.allocation == Decimal("8300")


def test_weight_cash_reserve_portfolio_risk_and_sector_caps() -> None:
    sizer = AtrRiskPositionSizer()
    assert (
        sizer.size(
            context(execution_price=Decimal("250"), atr=Decimal("1")), PortfolioRiskConfig()
        ).shares
        == 40
    )
    cash_limited = sizer.size(
        context(cash=Decimal("10500"), atr=Decimal("1")), PortfolioRiskConfig()
    )
    assert cash_limited.shares == 5
    assert cash_limited.reason == PortfolioDecisionReason.BUY_APPROVED
    reserve_blocked = sizer.size(context(cash=Decimal("10000")), PortfolioRiskConfig())
    assert reserve_blocked.reason == PortfolioDecisionReason.CASH_RESERVE
    risk_blocked = sizer.size(
        context(current_portfolio_risk=Decimal("8000")), PortfolioRiskConfig()
    )
    assert risk_blocked.reason == PortfolioDecisionReason.PORTFOLIO_RISK_LIMIT
    sector_blocked = sizer.size(
        context(sector_market_value=Decimal("30000")), PortfolioRiskConfig()
    )
    assert sector_blocked.reason == PortfolioDecisionReason.SECTOR_LIMIT


def test_missing_and_invalid_atr_are_stable() -> None:
    sizer = AtrRiskPositionSizer()
    assert (
        sizer.size(context(atr=None), PortfolioRiskConfig()).reason
        == PortfolioDecisionReason.INSUFFICIENT_HISTORY
    )
    assert (
        sizer.size(context(atr=Decimal("0")), PortfolioRiskConfig()).reason
        == PortfolioDecisionReason.INVALID_RISK_DISTANCE
    )


def volatility_candidate(
    ticker: str,
    atr: Decimal | None,
    *,
    price: Decimal = Decimal("100"),
    sector: str = "Technology",
) -> VolatilitySizingCandidate:
    return VolatilitySizingCandidate(ticker, price, atr, sector)


def batch_context(**changes: object) -> VolatilityBatchContext:
    values: dict[str, object] = {
        "equity": Decimal("100000"),
        "cash": Decimal("100000"),
        "invested_value": Decimal("0"),
        "current_portfolio_risk": Decimal("0"),
        "sector_market_values": {},
        "available_slots": 10,
    }
    values.update(changes)
    return VolatilityBatchContext(**values)  # type: ignore[arg-type]


def test_atr_percentage_inverse_weights_and_normalization() -> None:
    sizer = AtrVolatilityNormalizedPositionSizer()
    assert sizer.atr_percentage(Decimal("2"), Decimal("100")) == Decimal("0.02")
    weights = sizer.normalized_weights(
        [volatility_candidate("LOW", Decimal("2")), volatility_candidate("HIGH", Decimal("4"))]
    )
    assert weights["LOW"] > weights["HIGH"]
    assert sum(weights.values(), Decimal("0")) == Decimal("1")
    assert weights["LOW"] == Decimal("2") / Decimal("3")


def test_volatility_batch_respects_weight_reserve_shared_cash_and_whole_shares() -> None:
    candidates = [
        volatility_candidate(str(index), Decimal(index + 1), sector=f"Sector {index}")
        for index in range(10)
    ]
    result = AtrVolatilityNormalizedPositionSizer().allocate(
        batch_context(), candidates, PortfolioRiskConfig()
    )
    approved = [item.decision for item in result if item.decision.shares > 0]
    assert approved
    assert all(item.position_weight_pct <= Decimal("10") for item in approved)
    assert all(isinstance(item.shares, int) for item in approved)
    assert sum((item.allocation for item in approved), Decimal("0")) <= Decimal("90000")


def test_volatility_batch_preserves_risk_sector_and_missing_history_rules() -> None:
    sizer = AtrVolatilityNormalizedPositionSizer()
    risk_limited = sizer.allocate(
        batch_context(available_slots=1),
        [volatility_candidate("RISK", Decimal("50"))],
        PortfolioRiskConfig(),
    )[0]
    assert risk_limited.decision.shares == 80
    assert risk_limited.decision.modeled_risk == Decimal("8000")
    sector_limited = sizer.allocate(
        batch_context(sector_market_values={"Technology": Decimal("30000")}, available_slots=1),
        [volatility_candidate("SECTOR", Decimal("5"))],
        PortfolioRiskConfig(),
    )[0]
    assert sector_limited.decision.reason == PortfolioDecisionReason.SECTOR_LIMIT
    missing = sizer.allocate(
        batch_context(available_slots=1),
        [volatility_candidate("MISSING", None)],
        PortfolioRiskConfig(),
    )[0]
    assert missing.normalized_weight is None
    assert missing.decision.reason == PortfolioDecisionReason.INSUFFICIENT_HISTORY


def test_volatility_batch_is_rank_ordered_and_deterministic() -> None:
    candidates = [
        volatility_candidate("FIRST", Decimal("2"), sector="A"),
        volatility_candidate("SECOND", Decimal("3"), sector="B"),
    ]
    sizer = AtrVolatilityNormalizedPositionSizer()
    first = sizer.allocate(batch_context(available_slots=1), candidates, PortfolioRiskConfig())
    second = sizer.allocate(batch_context(available_slots=1), candidates, PortfolioRiskConfig())
    assert first == second
    assert first[0].decision.reason == PortfolioDecisionReason.BUY_APPROVED
    assert first[1].decision.reason == PortfolioDecisionReason.RANKING_NOT_SELECTED
