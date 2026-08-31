from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.decisions import CurrentPortfolioState, PortfolioStatePosition
from alphapilot.portfolio.exit_guidance import StrategyExitState
from alphapilot.portfolio.orchestration import (
    CandidateDataStatus,
    PlanReadinessStatus,
    PortfolioDecisionOrchestrator,
)
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def company(ticker: str, sector: str | None = "Technology") -> Company:
    return Company(
        id=uuid4(),
        ticker=ticker,
        name=ticker,
        exchange="NASDAQ",
        sector=sector,
        is_active=True,
    )


def candles(company_id: UUID, end: date, *, close_step: Decimal) -> list[DailyCandle]:
    result = []
    for offset in range(220):
        day = end - timedelta(days=219 - offset)
        close = Decimal("100") + Decimal(offset) * close_step
        result.append(
            DailyCandle(
                company_id=company_id,
                trading_day=day,
                open=close,
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                volume=1000,
            )
        )
    return result


class FakeCompanyService:
    def __init__(self, companies: dict[str, Company]) -> None:
        self.companies = companies
        self.calls: list[str] = []
        self.list_calls = 0

    async def get_company(self, ticker: str) -> Company | None:
        self.calls.append(ticker)
        return self.companies.get(ticker)

    async def list_companies(self) -> list[Company]:
        self.list_calls += 1
        return list(self.companies.values())


class FakeCandleService:
    def __init__(self, histories: dict[UUID, list[DailyCandle]]) -> None:
        self.histories = histories
        self.calls: list[tuple[UUID, date, date]] = []
        self.bulk_calls: list[tuple[list[UUID], date, date]] = []

    async def get_history(self, company_id: UUID, start: date, end: date) -> list[DailyCandle]:
        self.calls.append((company_id, start, end))
        return list(self.histories.get(company_id, []))

    async def get_histories(
        self, company_ids: list[UUID], start: date, end: date
    ) -> dict[UUID, list[DailyCandle]]:
        self.bulk_calls.append((company_ids, start, end))
        return {company_id: list(self.histories.get(company_id, [])) for company_id in company_ids}


class FakeUniverse:
    def __init__(self) -> None:
        self.calls = 0

    async def list_active(self, index_symbol: str) -> list[SimpleNamespace]:
        self.calls += 1
        assert index_symbol == "^GSPC"
        return [SimpleNamespace(ticker="AAA")]


@pytest.mark.asyncio
async def test_bulk_market_snapshot_is_loaded_once_and_reused_without_semantic_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY", "ETF")
    stock = company("AAA", "Industrials")
    histories = {
        spy.id: candles(spy.id, as_of, close_step=Decimal("0.1")),
        stock.id: candles(stock.id, as_of, close_step=Decimal("0.2")),
    }
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysBuyStrategy(),
    )
    state = CurrentPortfolioState(cash=Decimal("100000"))
    company_service = FakeCompanyService({"SPY": spy, "AAA": stock})
    candle_service = FakeCandleService(histories)
    universe = FakeUniverse()
    orchestrator = PortfolioDecisionOrchestrator(company_service, candle_service, universe)
    snapshot = await orchestrator.load_market_snapshot(state=state, requested_as_of_date=as_of)
    first = await orchestrator.build_plan(
        state=state,
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
        market_snapshot=snapshot,
    )
    second = await orchestrator.build_plan(
        state=state,
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
        market_snapshot=snapshot,
    )
    direct = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService(histories),
        FakeUniverse(),
    ).build_plan(
        state=state,
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
    )
    assert first.plan == second.plan
    assert first.statuses == second.statuses
    assert first.plan == direct.plan
    assert first.statuses == direct.statuses
    assert company_service.list_calls == 1
    assert company_service.calls == []
    assert len(candle_service.bulk_calls) == 1
    assert candle_service.calls == []
    assert universe.calls == 1


class AlwaysBuyStrategy:
    def evaluate(
        self, company: Company, candles: list[DailyCandle], context: object
    ) -> StrategyEvaluation:
        assert candles
        assert context is not None
        return StrategyEvaluation(Signal.BUY, SignalReason.EMA20_PULLBACK_RECLAIM)


class AlwaysHoldStrategy:
    def evaluate(
        self, company: Company, candles: list[DailyCandle], context: object
    ) -> StrategyEvaluation:
        assert candles
        assert context is not None
        return StrategyEvaluation(Signal.HOLD, SignalReason.NO_PULLBACK)


@pytest.mark.asyncio
async def test_orchestrator_loads_and_calculates_signal_rs20_atr_and_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY", "ETF")
    stock = company("AAA", "Industrials")
    company_service = FakeCompanyService({"SPY": spy, "AAA": stock})
    candle_service = FakeCandleService(
        {
            spy.id: candles(spy.id, as_of, close_step=Decimal("0.1")),
            stock.id: candles(stock.id, as_of, close_step=Decimal("0.2")),
        }
    )
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysBuyStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        company_service, candle_service, FakeUniverse()
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
    )
    assert company_service.calls == ["SPY", "AAA"]
    assert len(candle_service.calls) == 2
    assert result.analysis_as_of_date == as_of
    assert result.statuses[0].status == CandidateDataStatus.READY
    assert result.statuses[0].company_name == "AAA"
    assert result.statuses[0].sector == "Industrials"
    assert result.statuses[0].ranking_score is not None
    assert result.statuses[0].atr == Decimal("4")
    assert result.statuses[0].decision is not None
    assert result.statuses[0].decision_reason is not None
    assert result.statuses[0].candidate_rank == 1
    decision = result.plan.decisions[0]
    assert decision.signal == Signal.BUY
    assert decision.ranking_score is not None
    assert decision.atr == Decimal("4")
    assert decision.sector == "Industrials"
    assert decision.proposed_shares > 0
    assert result.readiness.status == PlanReadinessStatus.READY
    assert result.readiness.requested_tickers == 1
    assert result.readiness.evaluated_tickers == 1
    assert result.readiness.approved_buys == 1


@pytest.mark.asyncio
async def test_orchestrator_filters_future_data_and_reports_stale_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY")
    stock = company("AAA")
    spy_history = candles(spy.id, as_of, close_step=Decimal("0.1"))
    stock_history = candles(stock.id, as_of - timedelta(days=1), close_step=Decimal("0.2"))
    stock_history.append(
        DailyCandle(
            company_id=stock.id,
            trading_day=as_of + timedelta(days=1),
            open=Decimal("999"),
            high=Decimal("999"),
            low=Decimal("999"),
            close=Decimal("999"),
            volume=1000,
        )
    )
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysBuyStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService({spy.id: spy_history, stock.id: stock_history}),
        FakeUniverse(),
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
    )
    assert result.statuses[0].status == CandidateDataStatus.STALE_DATA
    assert result.statuses[0].data_as_of_date == as_of - timedelta(days=1)
    assert result.plan.decisions == ()
    assert result.readiness.status == PlanReadinessStatus.DATA_NOT_READY
    assert result.readiness.stale_tickers == 1
    assert result.readiness.evaluated_tickers == 0


@pytest.mark.asyncio
async def test_all_fresh_zero_buy_is_no_action_not_data_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY")
    stock = company("AAA")
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysHoldStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService(
            {
                spy.id: candles(spy.id, as_of, close_step=Decimal("0.1")),
                stock.id: candles(stock.id, as_of, close_step=Decimal("0.2")),
            }
        ),
        FakeUniverse(),
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
    )

    assert result.statuses[0].status == CandidateDataStatus.NO_ACTION
    assert result.readiness.status == PlanReadinessStatus.NO_ACTION
    assert result.readiness.requested_tickers == 1
    assert result.readiness.evaluated_tickers == 1
    assert result.readiness.fresh_tickers == 1
    assert result.readiness.stale_tickers == 0
    assert result.readiness.buy_signals == 0
    assert result.readiness.approved_buys == 0


@pytest.mark.asyncio
async def test_held_position_exit_context_uses_only_candles_through_analysis_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY")
    stock = company("AAA")
    stock_history = candles(stock.id, as_of, close_step=Decimal("0.2"))
    expected_close = stock_history[-1].close
    stock_history.append(
        DailyCandle(
            company_id=stock.id,
            trading_day=as_of + timedelta(days=1),
            open=Decimal("999"),
            high=Decimal("999"),
            low=Decimal("999"),
            close=Decimal("999"),
            volume=1000,
        )
    )

    class ContextStrategy:
        def evaluate(
            self, company: Company, candles: list[DailyCandle], context: object
        ) -> StrategyEvaluation:
            del company, context
            assert candles[-1].trading_day == as_of
            return StrategyEvaluation(
                Signal.HOLD,
                SignalReason.NO_PULLBACK,
                ema20=expected_close - Decimal("1"),
                ema50=expected_close - Decimal("5"),
            )

    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: ContextStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService(
            {
                spy.id: candles(spy.id, as_of, close_step=Decimal("0.1")),
                stock.id: stock_history,
            }
        ),
        FakeUniverse(),
    ).build_plan(
        state=CurrentPortfolioState(
            cash=Decimal("90000"),
            positions=(PortfolioStatePosition("AAA", 100, expected_close),),
        ),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
    )
    exit_context = result.plan.decisions[0].exit_context
    assert exit_context is not None
    assert exit_context.data_as_of_date == as_of
    assert exit_context.reference_close == expected_close
    assert exit_context.current_exit_state == StrategyExitState.ABOVE_EMA20


@pytest.mark.asyncio
async def test_explicit_scope_accepts_custom_ticker_while_blank_scope_stays_sp500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY", "ETF")
    constituent = company("AAA")
    custom = company("SBET", None)
    held = company("LDOS", "Industrials")
    custom.is_custom_tracked = True
    companies = FakeCompanyService({"SPY": spy, "AAA": constituent, "SBET": custom, "LDOS": held})
    histories = {
        spy.id: candles(spy.id, as_of, close_step=Decimal("0.1")),
        constituent.id: candles(constituent.id, as_of, close_step=Decimal("0.2")),
        custom.id: candles(custom.id, as_of, close_step=Decimal("0.3")),
        held.id: candles(held.id, as_of, close_step=Decimal("0.15")),
    }
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysBuyStrategy(),
    )
    orchestrator = PortfolioDecisionOrchestrator(
        companies, FakeCandleService(histories), FakeUniverse()
    )
    explicit = await orchestrator.build_plan(
        state=CurrentPortfolioState(
            cash=Decimal("90000"),
            positions=(PortfolioStatePosition("LDOS", 10, Decimal("100")),),
        ),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
        tickers=("sbet",),
    )
    assert [item.ticker for item in explicit.statuses] == ["LDOS", "SBET"]
    target = next(item for item in explicit.statuses if item.ticker == "SBET")
    assert target.is_custom_tracked is True
    assert target.company_id == custom.id
    assert explicit.evaluation_target_ticker == "SBET"
    assert {item.ticker for item in explicit.plan.decisions} == {"LDOS", "SBET"}

    companies.calls.clear()
    blank = await orchestrator.build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
    )
    assert [item.ticker for item in blank.statuses] == ["AAA"]
    assert "SBET" not in companies.calls


@pytest.mark.asyncio
async def test_missing_explicit_target_keeps_its_identity_with_held_portfolio_context() -> None:
    as_of = date(2026, 8, 20)
    spy = company("SPY", "ETF")
    held = company("LDOS", "Industrials")
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "LDOS": held}),
        FakeCandleService(
            {
                spy.id: candles(spy.id, as_of, close_step=Decimal("0.1")),
                held.id: candles(held.id, as_of, close_step=Decimal("0.2")),
            }
        ),
        FakeUniverse(),
    ).build_plan(
        state=CurrentPortfolioState(
            cash=Decimal("90000"),
            positions=(PortfolioStatePosition("LDOS", 10, Decimal("100")),),
        ),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=as_of,
        tickers=("missing",),
    )

    assert result.evaluation_target_ticker == "MISSING"
    assert [item.ticker for item in result.statuses] == ["LDOS", "MISSING"]
    missing = result.statuses[-1]
    assert missing.status == CandidateDataStatus.COMPANY_NOT_FOUND
    assert missing.company_name is None
    assert missing.company_id is None


@pytest.mark.asyncio
async def test_weekend_uses_prior_spy_session_and_partial_data_reconciles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    friday = date(2026, 8, 21)
    sunday = date(2026, 8, 23)
    spy = company("SPY")
    fresh = company("AAA")
    stale = company("BBB")

    class TwoStocks:
        async def list_active(self, index_symbol: str) -> list[SimpleNamespace]:
            assert index_symbol == "^GSPC"
            return [SimpleNamespace(ticker="AAA"), SimpleNamespace(ticker="BBB")]

    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysBuyStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": fresh, "BBB": stale}),
        FakeCandleService(
            {
                spy.id: candles(spy.id, friday, close_step=Decimal("0.1")),
                fresh.id: candles(fresh.id, friday, close_step=Decimal("0.2")),
                stale.id: candles(stale.id, friday - timedelta(days=1), close_step=Decimal("0.2")),
            }
        ),
        TwoStocks(),
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=sunday,
    )

    assert result.analysis_as_of_date == friday
    assert result.statuses[0].status == CandidateDataStatus.READY
    assert result.statuses[1].status == CandidateDataStatus.STALE_DATA
    assert result.readiness.status == PlanReadinessStatus.PARTIAL_DATA
    assert result.readiness.requested_tickers == 2
    assert result.readiness.evaluated_tickers == 1
    assert result.readiness.fresh_tickers == 1
    assert result.readiness.stale_tickers == 1


@pytest.mark.asyncio
async def test_open_current_session_is_excluded_from_all_candidate_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = date(2026, 8, 26)
    completed = date(2026, 8, 25)
    spy = company("SPY", "ETF")
    stock = company("AAA", "Technology")
    spy_history = candles(spy.id, completed, close_step=Decimal("0.1"))
    stock_history = candles(stock.id, completed, close_step=Decimal("0.2"))
    expected_close = stock_history[-1].close
    for company_id, history in ((spy.id, spy_history), (stock.id, stock_history)):
        history.append(
            DailyCandle(
                company_id=company_id,
                trading_day=requested,
                open=Decimal("999"),
                high=Decimal("1000"),
                low=Decimal("1"),
                close=Decimal("999"),
                volume=1,
            )
        )

    class InspectingStrategy:
        def evaluate(
            self, company: Company, candles: list[DailyCandle], context: object
        ) -> StrategyEvaluation:
            del company, context
            assert candles[-1].trading_day == completed
            assert candles[-1].close == expected_close
            return StrategyEvaluation(Signal.BUY, SignalReason.EMA20_PULLBACK_RECLAIM)

    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: InspectingStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService({spy.id: spy_history, stock.id: stock_history}),
        FakeUniverse(),
        session_policy=CompletedDailySessionPolicy(
            now_provider=lambda: datetime(2026, 8, 26, 18, 0, tzinfo=UTC)
        ),
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.ATR_RISK,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=requested,
        tickers=("AAA",),
    )

    assert result.requested_as_of_date == requested
    assert result.analysis_as_of_date == completed
    assert result.statuses[0].data_as_of_date == completed
    decision = result.plan.decisions[0]
    assert decision.reference_price == expected_close
    assert decision.ranking_score is not None
    assert decision.atr == Decimal("4")
    assert decision.exit_context is not None
    assert decision.exit_context.data_as_of_date == completed


@pytest.mark.asyncio
async def test_completed_current_session_can_be_selected_for_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = date(2026, 8, 26)
    spy = company("SPY", "ETF")
    stock = company("AAA")
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysHoldStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService(
            {
                spy.id: candles(spy.id, requested, close_step=Decimal("0.1")),
                stock.id: candles(stock.id, requested, close_step=Decimal("0.2")),
            }
        ),
        FakeUniverse(),
        session_policy=CompletedDailySessionPolicy(
            now_provider=lambda: datetime(2026, 8, 26, 20, 16, tzinfo=UTC)
        ),
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=requested,
    )

    assert result.analysis_as_of_date == requested
    assert result.statuses[0].data_as_of_date == requested


@pytest.mark.asyncio
async def test_us_market_holiday_resolves_to_prior_stored_spy_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holiday = date(2026, 7, 3)  # Independence Day observed
    completed = date(2026, 7, 2)
    spy = company("SPY", "ETF")
    stock = company("AAA")
    monkeypatch.setattr(
        "alphapilot.portfolio.orchestration.create_strategy",
        lambda *args, **kwargs: AlwaysHoldStrategy(),
    )
    result = await PortfolioDecisionOrchestrator(
        FakeCompanyService({"SPY": spy, "AAA": stock}),
        FakeCandleService(
            {
                spy.id: candles(spy.id, completed, close_step=Decimal("0.1")),
                stock.id: candles(stock.id, completed, close_step=Decimal("0.2")),
            }
        ),
        FakeUniverse(),
    ).build_plan(
        state=CurrentPortfolioState(cash=Decimal("100000")),
        strategy_name=StrategyName.EMA20_PULLBACK,
        selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
        sizing_policy=SizingPolicyName.EQUAL_SLOT,
        risk_config=PortfolioRiskConfig(),
        requested_as_of_date=holiday,
    )

    assert result.analysis_as_of_date == completed
    assert result.statuses[0].data_as_of_date == completed
