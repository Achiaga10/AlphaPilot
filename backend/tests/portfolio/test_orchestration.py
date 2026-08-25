from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.portfolio.decisions import CurrentPortfolioState
from alphapilot.portfolio.orchestration import (
    CandidateDataStatus,
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

    async def get_company(self, ticker: str) -> Company | None:
        self.calls.append(ticker)
        return self.companies.get(ticker)


class FakeCandleService:
    def __init__(self, histories: dict[UUID, list[DailyCandle]]) -> None:
        self.histories = histories
        self.calls: list[tuple[UUID, date, date]] = []

    async def get_history(self, company_id: UUID, start: date, end: date) -> list[DailyCandle]:
        self.calls.append((company_id, start, end))
        return list(self.histories.get(company_id, []))


class FakeUniverse:
    async def list_active(self, index_symbol: str) -> list[SimpleNamespace]:
        assert index_symbol == "^GSPC"
        return [SimpleNamespace(ticker="AAA")]


class AlwaysBuyStrategy:
    def evaluate(
        self, company: Company, candles: list[DailyCandle], context: object
    ) -> StrategyEvaluation:
        assert candles
        assert context is not None
        return StrategyEvaluation(Signal.BUY, SignalReason.EMA20_PULLBACK_RECLAIM)


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
    decision = result.plan.decisions[0]
    assert decision.signal == Signal.BUY
    assert decision.ranking_score is not None
    assert decision.atr == Decimal("4")
    assert decision.sector == "Industrials"
    assert decision.proposed_shares > 0


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
