from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from alphapilot.api.routes.portfolio import get_daily_portfolio_brief_service
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.daily_brief import DailyBriefReadiness
from alphapilot.portfolio.decisions import PortfolioDecision, PortfolioDecisionPlan
from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
)
from alphapilot.portfolio.exit_guidance import StrategyExitContext, StrategyExitState
from alphapilot.portfolio.sizing import PortfolioDecisionReason, PortfolioDecisionType
from alphapilot.services.daily_market_scheduler import DailySchedulerStatus, DailySyncStatus
from alphapilot.services.daily_portfolio_brief import DailyPortfolioBriefService
from alphapilot.services.research_portfolio import (
    PortfolioValuationStatus,
    PositionValuation,
    ResearchPortfolioValuation,
)
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal

DAY = date(2026, 8, 28)


def _position(ticker: str, profile: str | None = "micho-150-v1") -> PositionValuation:
    return PositionValuation(
        uuid4(),
        uuid4(),
        ticker,
        "Industrials",
        "OPEN",
        10,
        Decimal("100"),
        Decimal("1000"),
        DAY,
        Decimal("100"),
        "micho-150" if profile else None,
        profile,
        1 if profile else None,
        "relative-strength-20" if profile else None,
        "PLAN_PROFILE" if profile else "LEGACY_IMPORTED",
        Decimal("100") if profile else Decimal("0"),
        DAY,
        Decimal("110"),
        Decimal("1100"),
        None,
        Decimal("100"),
        Decimal("10"),
        "VALUED",
    )


def _intelligence(position: PositionValuation, status: str | None, *, sticky: bool = False):
    profile = position.strategy_profile_id
    available = profile is not None
    reason = {
        "SELL": "SMA150_BREAKDOWN",
        "ATTENTION": "SMA150_INTRADAY_BREACH_RECOVERED",
        "HOLD": "SMA150_HELD",
    }.get(status, "STRATEGY_GUIDANCE_UNAVAILABLE")
    return SimpleNamespace(
        position_id=position.position_id,
        ticker=position.ticker,
        company_name=f"{position.ticker} Company",
        strategy=position.strategy,
        strategy_profile_id=profile,
        strategy_profile_version=position.strategy_profile_version,
        monitoring_status=status,
        monitoring_reason=reason,
        explanation=f"{position.ticker} {status or 'guidance unavailable'}",
        quantity=position.quantity,
        latest_completed_close=position.latest_completed_close,
        unrealized_pnl=position.unrealized_pnl,
        unrealized_pnl_pct=position.unrealized_pnl_pct,
        monitoring_completed_trading_day=DAY,
        exit_triggered=sticky,
        exit_triggered_on=DAY if sticky else None,
        strategy_guidance_available=available,
        indicator_facts={"sma150": "105"} if available else {},
        protective_stop_policy="NONE" if available else "UNAVAILABLE",
        trailing_stop_policy="NONE" if available else "UNAVAILABLE",
        profit_target_policy="NONE" if available else "UNAVAILABLE",
        research_only_stop_candidate=None,
        research_only_stop_status="NOT_ACTIVE" if available else None,
    )


def _decision(strategy: StrategyName) -> PortfolioDecision:
    micho = strategy == StrategyName.MICHO_150
    context = StrategyExitContext(
        strategy,
        DAY,
        Decimal("120"),
        Signal.BUY,
        "BUY_SETUP",
        "close-below-sma150" if micho else "hybrid-2%",
        StrategyExitState.ABOVE_SMA150 if micho else StrategyExitState.ABOVE_EMA20,
        ema20=None if micho else Decimal("115"),
        ema50=None if micho else Decimal("105"),
        sma150=Decimal("108") if micho else None,
    )
    return PortfolioDecision(
        "MCHO" if micho else "EMA",
        Signal.BUY,
        PortfolioDecisionType.BUY,
        PortfolioDecisionReason.BUY_APPROVED,
        Decimal("0.10"),
        Decimal("120"),
        Decimal("4"),
        Decimal("8"),
        Decimal("1000"),
        Decimal("9600"),
        Decimal("9.6"),
        80,
        Decimal("960"),
        "Industrials",
        Decimal("0"),
        Decimal("9.6"),
        0,
        None,
        action_id=f"1:BUY:{'MCHO' if micho else 'EMA'}",
        exit_context=context,
        execution_readiness=(
            ExecutionReadiness.ACTIONABLE if micho else ExecutionReadiness.RESEARCH_ONLY
        ),
        execution_readiness_reason=(
            ExecutionReadinessReason.LOSS_CONTROL_READY
            if micho
            else ExecutionReadinessReason.NO_APPROVED_LOSS_CONTROL_POLICY
        ),
        loss_control_policy="SMA150_COMPLETED_CLOSE_EXIT" if micho else "NONE",
        loss_control_boundary_price=Decimal("108") if micho else None,
        loss_control_trigger="COMPLETED_DAILY_CLOSE_BELOW" if micho else None,
        loss_control_active=micho,
        loss_control_broker_stop_order=False,
    )


class FakePortfolios:
    def __init__(self, valuation: ResearchPortfolioValuation):
        self.valuation = valuation

    async def value(self, _portfolio_id):
        return self.valuation


class FakeIntelligence:
    def __init__(self, values):
        self.values = values

    async def get_position_intelligence(self, _portfolio_id, position_id):
        return self.values[position_id]

    async def get_portfolio_intelligence(self, _portfolio_id, *, valuation):
        assert {item.position_id for item in valuation.positions} == set(self.values)
        return tuple(self.values[item.position_id] for item in valuation.positions)


class FakeFreshness:
    def __init__(self, *, stale=0, no_data=0, latest=DAY):
        self.value = SimpleNamespace(
            latest_spy_date=latest,
            stale_tracked_ticker_count=stale,
            no_data_tracked_ticker_count=no_data,
        )

    async def get_freshness(self):
        return self.value


class FakeOrchestrator:
    def __init__(self, *, now: datetime | None = None):
        self.calls = 0
        self.call_arguments = []
        self.snapshot_calls = 0
        self.session_policy = CompletedDailySessionPolicy(
            now_provider=(lambda: now)
            if now is not None
            else lambda: datetime(2026, 8, 31, 12, tzinfo=UTC)
        )

    async def load_market_snapshot(self, **kwargs):
        self.snapshot_calls += 1
        return SimpleNamespace(analysis_as_of_date=DAY)

    async def build_plan(self, **kwargs):
        self.calls += 1
        self.call_arguments.append(kwargs)
        decision = _decision(kwargs["strategy_name"])
        return SimpleNamespace(
            plan=PortfolioDecisionPlan(
                Decimal("100000"),
                Decimal("30000"),
                Decimal("10000"),
                Decimal("100"),
                Decimal("7900"),
                4,
                (decision,),
            ),
            analysis_as_of_date=DAY,
        )


def _valuation(positions, status=PortfolioValuationStatus.COMPLETE):
    return ResearchPortfolioValuation(
        uuid4(),
        "default",
        "Research",
        7,
        Decimal("30000"),
        Decimal("0"),
        sum((item.cost_basis for item in positions), Decimal("0")),
        Decimal("4400") if status == PortfolioValuationStatus.COMPLETE else None,
        Decimal("34400") if status == PortfolioValuationStatus.COMPLETE else None,
        Decimal("87.2") if status == PortfolioValuationStatus.COMPLETE else None,
        Decimal("12.8") if status == PortfolioValuationStatus.COMPLETE else None,
        Decimal("400") if status == PortfolioValuationStatus.COMPLETE else None,
        DAY,
        status,
        tuple(positions),
    )


@pytest.mark.asyncio
async def test_daily_brief_prioritizes_sticky_sell_and_defers_actionable_entries() -> None:
    sell, attention, hold, unknown = (
        _position("SELL"),
        _position("ATTN"),
        _position("HOLD"),
        _position("UNKN", None),
    )
    valuation = _valuation([sell, attention, hold, unknown])
    intelligence = {
        sell.position_id: _intelligence(sell, "HOLD", sticky=True),
        attention.position_id: _intelligence(attention, "ATTENTION"),
        hold.position_id: _intelligence(hold, "HOLD"),
        unknown.position_id: _intelligence(unknown, None),
    }
    service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence(intelligence),
        FakeOrchestrator(),
        FakeFreshness(),
        DailySchedulerStatus(enabled=False),
    )
    brief = await service.build(valuation.portfolio_id)

    assert [item.ticker for item in brief.required_actions] == ["SELL"]
    assert [item.ticker for item in brief.attention_positions] == ["ATTN"]
    assert [item.ticker for item in brief.hold_positions] == ["HOLD"]
    assert [item.ticker for item in brief.unavailable_positions] == ["UNKN"]
    assert brief.workflow_status == "WAITING_FOR_REQUIRED_EXITS"
    assert brief.actionable_opportunities == ()
    micho = next(item for item in brief.deferred_opportunities if item.ticker == "MCHO")
    assert micho.execution_readiness == "ACTIONABLE"
    assert micho.loss_control_boundary == Decimal("108")
    assert micho.loss_control_distance_dollars == Decimal("12")
    assert micho.loss_control_trigger == "COMPLETED_DAILY_CLOSE_BELOW"
    assert not micho.broker_stop_order
    assert brief.summary.cash == Decimal("30000")


@pytest.mark.asyncio
async def test_daily_brief_keeps_ema_research_only_and_micho_actionable() -> None:
    valuation = _valuation([])
    orchestrator = FakeOrchestrator()
    service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence({}),
        orchestrator,
        FakeFreshness(),
        DailySchedulerStatus(enabled=False),
    )
    brief = await service.build(valuation.portfolio_id)
    assert brief.data_status.readiness == DailyBriefReadiness.READY
    assert [item.ticker for item in brief.actionable_opportunities] == ["MCHO"]
    assert [item.ticker for item in brief.research_only_opportunities] == ["EMA"]
    ema = brief.research_only_opportunities[0]
    assert ema.execution_readiness_reason == "NO_APPROVED_LOSS_CONTROL_POLICY"
    assert ema.loss_control_boundary is None
    assert [item.reference_type for item in ema.strategy_references] == [
        "EMA20_PULLBACK_REFERENCE",
        "EMA50_HARD_BREAKDOWN",
    ]
    assert all(
        call["evaluate_existing_position_exits"] is False for call in orchestrator.call_arguments
    )
    assert orchestrator.snapshot_calls == 1


@pytest.mark.asyncio
async def test_missing_expected_completed_weekday_blocks_new_entries() -> None:
    valuation = _valuation([])
    orchestrator = FakeOrchestrator(now=datetime(2026, 9, 1, 20, tzinfo=UTC))
    service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence({}),
        orchestrator,
        FakeFreshness(latest=DAY),
        DailySchedulerStatus(enabled=False),
    )
    core = await service.build_core(valuation.portfolio_id)
    assert core.data_status.expected_completed_session == date(2026, 8, 31)
    assert core.data_status.readiness == DailyBriefReadiness.BLOCKED
    assert "EXPECTED_COMPLETED_SESSION_NOT_STORED" in core.blockers
    opportunities = await service.build_opportunities(valuation.portfolio_id)
    assert opportunities.actionable_opportunities == ()
    assert orchestrator.snapshot_calls == 0


@pytest.mark.asyncio
async def test_daily_brief_fails_closed_when_actionable_buy_lacks_loss_control() -> None:
    valuation = _valuation([])

    class InvalidOrchestrator(FakeOrchestrator):
        async def build_plan(self, **kwargs):
            result = await super().build_plan(**kwargs)
            decision = result.plan.decisions[0]
            if kwargs["strategy_name"] == StrategyName.MICHO_150:
                invalid = replace(decision, loss_control_boundary_price=None)
                return SimpleNamespace(
                    plan=replace(result.plan, decisions=(invalid,)),
                    analysis_as_of_date=result.analysis_as_of_date,
                )
            return result

    service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence({}),
        InvalidOrchestrator(),
        FakeFreshness(),
        DailySchedulerStatus(enabled=False),
    )
    with pytest.raises(ValueError, match="lacks deterministic numeric loss-control"):
        await service.build(valuation.portfolio_id)


@pytest.mark.asyncio
async def test_failed_sync_blocks_actionable_but_preserves_actual_position_session() -> None:
    hold = _position("HOLD")
    valuation = _valuation([hold])
    scheduler = DailySchedulerStatus(enabled=True, last_status=DailySyncStatus.FAILED)
    service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence({hold.position_id: _intelligence(hold, "HOLD")}),
        FakeOrchestrator(),
        FakeFreshness(),
        scheduler,
    )
    brief = await service.build(valuation.portfolio_id)
    assert brief.data_status.readiness == DailyBriefReadiness.BLOCKED
    assert brief.actionable_opportunities == ()
    assert brief.hold_positions[0].as_of_session == DAY
    assert "LATEST_DAILY_SYNC_FAILED" in brief.blockers


@pytest.mark.asyncio
async def test_incomplete_valuation_blocks_plans_without_fabricating_zero_facts() -> None:
    missing = _position("MISS")
    missing = replace(
        missing,
        latest_completed_trading_day=None,
        latest_completed_close=None,
        market_value=None,
        unrealized_pnl=None,
        unrealized_pnl_pct=None,
        valuation_status="PRICE_UNAVAILABLE",
    )
    valuation = _valuation([missing], PortfolioValuationStatus.PARTIAL)
    orchestrator = FakeOrchestrator()
    service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence({missing.position_id: _intelligence(missing, "HOLD")}),
        orchestrator,
        FakeFreshness(),
        DailySchedulerStatus(enabled=False),
    )
    brief = await service.build(valuation.portfolio_id)
    assert brief.data_status.readiness == DailyBriefReadiness.BLOCKED
    assert brief.summary.portfolio_value is None
    assert brief.summary.modeled_risk_dollars == Decimal("100")
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_daily_brief_api_is_typed_and_read_only(client) -> None:
    valuation = _valuation([])
    daily_service = DailyPortfolioBriefService(
        FakePortfolios(valuation),
        FakeIntelligence({}),
        FakeOrchestrator(),
        FakeFreshness(),
        DailySchedulerStatus(enabled=False),
    )
    brief = await daily_service.build_core(valuation.portfolio_id)
    opportunities = await daily_service.build_opportunities(
        valuation.portfolio_id, research_only_limit=10
    )

    class Service:
        async def build_core(self, _portfolio_id, *, requested_as_of_date=None):
            assert requested_as_of_date is None
            return brief

        async def build_opportunities(
            self,
            _portfolio_id,
            *,
            requested_as_of_date=None,
            research_only_limit=10,
        ):
            assert requested_as_of_date is None
            assert research_only_limit == 10
            return opportunities

    from alphapilot.main import app

    app.dependency_overrides[get_daily_portfolio_brief_service] = Service
    try:
        response = await client.get(f"/api/v1/portfolio/{valuation.portfolio_id}/daily-brief")
        opportunity_response = await client.get(
            f"/api/v1/portfolio/{valuation.portfolio_id}/daily-brief/opportunities"
        )
    finally:
        app.dependency_overrides.pop(get_daily_portfolio_brief_service, None)
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_revision"] == 7
    assert body["data_status"]["brief_session"] == DAY.isoformat()
    assert "actionable_opportunities" not in body
    assert opportunity_response.status_code == 200
    opportunity_body = opportunity_response.json()
    assert opportunity_body["actionable_total_count"] == 1
    assert opportunity_body["research_only_total_count"] == 1
    assert opportunity_body["research_only_limit"] == 10
