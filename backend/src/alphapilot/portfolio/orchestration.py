from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.backtesting.ranking_features import RelativeStrength20Calculator
from alphapilot.backtesting.service import CandleHistoryService, CompanyLookupService
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
    PortfolioDecisionPlan,
)
from alphapilot.portfolio.risk import AverageTrueRangeCalculator, PortfolioRiskConfig
from alphapilot.portfolio.sizing import PortfolioDecisionReason, SizingPolicyName
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.factory import create_strategy, get_strategy_stock_warmup_days
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


class ActiveUniverseRepository(Protocol):
    async def list_active(self, index_symbol: str) -> list[IndexConstituent]: ...


class CandidateDataStatus(StrEnum):
    READY = "READY"
    NO_ACTION = "NO_ACTION"
    COMPANY_NOT_FOUND = "COMPANY_NOT_FOUND"
    NO_DATA = "NO_DATA"
    STALE_DATA = "STALE_DATA"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


@dataclass(slots=True, frozen=True)
class CandidateOrchestrationStatus:
    ticker: str
    status: CandidateDataStatus
    data_as_of_date: date | None
    signal: Signal | None
    reason: str


@dataclass(slots=True, frozen=True)
class PortfolioOrchestrationResult:
    plan: PortfolioDecisionPlan
    requested_as_of_date: date
    analysis_as_of_date: date
    statuses: tuple[CandidateOrchestrationStatus, ...]


class PortfolioDecisionOrchestrator:
    SP500_INDEX_SYMBOL = "^GSPC"
    BENCHMARK_TICKER = "SPY"
    HISTORY_DAYS = 400

    def __init__(
        self,
        company_service: CompanyLookupService,
        candle_service: CandleHistoryService,
        universe_repository: ActiveUniverseRepository,
        decision_engine: PortfolioDecisionEngine | None = None,
    ) -> None:
        self.company_service = company_service
        self.candle_service = candle_service
        self.universe_repository = universe_repository
        self.decision_engine = decision_engine or PortfolioDecisionEngine()

    async def build_plan(
        self,
        *,
        state: CurrentPortfolioState,
        strategy_name: StrategyName,
        selection_policy: SelectionPolicyName,
        sizing_policy: SizingPolicyName,
        risk_config: PortfolioRiskConfig,
        requested_as_of_date: date,
        tickers: tuple[str, ...] | None = None,
        exit_mode: TrendExitMode = TrendExitMode.HYBRID,
        hybrid_trend_threshold_pct: Decimal = Decimal("2"),
        micho_entry_mode: MichoEntryMode = MichoEntryMode.BOTH,
    ) -> PortfolioOrchestrationResult:
        benchmark = await self.company_service.get_company(self.BENCHMARK_TICKER)
        if benchmark is None:
            raise ValueError("SPY benchmark company not found")
        benchmark_candles = await self.candle_service.get_history(
            benchmark.id,
            requested_as_of_date - timedelta(days=self.HISTORY_DAYS),
            requested_as_of_date,
        )
        if not benchmark_candles:
            raise ValueError("No stored SPY candles available on or before requested as-of date")
        benchmark_candles = sorted(
            (item for item in benchmark_candles if item.trading_day <= requested_as_of_date),
            key=lambda item: item.trading_day,
        )
        analysis_day = benchmark_candles[-1].trading_day
        strategy = create_strategy(
            strategy_name,
            exit_mode=exit_mode,
            hybrid_trend_threshold_pct=hybrid_trend_threshold_pct,
            micho_entry_mode=micho_entry_mode,
        )
        if tickers is None:
            constituents = await self.universe_repository.list_active(self.SP500_INDEX_SYMBOL)
            scope = {item.ticker.upper() for item in constituents}
        else:
            scope = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
        scope.update(position.ticker.upper() for position in state.positions)
        scope.discard(self.BENCHMARK_TICKER)
        context = StrategyContext(
            benchmark_ticker=self.BENCHMARK_TICKER,
            benchmark_candles=tuple(benchmark_candles),
        )
        ranking = RelativeStrength20Calculator()
        atr = AverageTrueRangeCalculator()
        candidates: list[PortfolioCandidate] = []
        statuses: list[CandidateOrchestrationStatus] = []
        history_days = max(self.HISTORY_DAYS, get_strategy_stock_warmup_days(strategy_name))

        for ticker in sorted(scope):
            company = await self.company_service.get_company(ticker)
            if company is None:
                statuses.append(
                    CandidateOrchestrationStatus(
                        ticker,
                        CandidateDataStatus.COMPANY_NOT_FOUND,
                        None,
                        None,
                        PortfolioDecisionReason.INSUFFICIENT_HISTORY.value,
                    )
                )
                continue
            candles = await self.candle_service.get_history(
                company.id,
                analysis_day - timedelta(days=history_days),
                analysis_day,
            )
            candles = sorted(
                (item for item in candles if item.trading_day <= analysis_day),
                key=lambda item: item.trading_day,
            )
            if not candles:
                statuses.append(
                    CandidateOrchestrationStatus(
                        ticker,
                        CandidateDataStatus.NO_DATA,
                        None,
                        None,
                        PortfolioDecisionReason.INSUFFICIENT_HISTORY.value,
                    )
                )
                continue
            latest = candles[-1]
            if latest.trading_day < analysis_day:
                statuses.append(
                    CandidateOrchestrationStatus(
                        ticker,
                        CandidateDataStatus.STALE_DATA,
                        latest.trading_day,
                        None,
                        PortfolioDecisionReason.STALE_DATA.value,
                    )
                )
                continue
            evaluation = strategy.evaluate(company, candles, context)
            score = (
                ranking.calculate(
                    stock_candles=candles,
                    benchmark_candles=benchmark_candles,
                    signal_day=analysis_day,
                )
                if evaluation.signal == Signal.BUY
                and selection_policy == SelectionPolicyName.RELATIVE_STRENGTH_20
                else None
            )
            atr_value = (
                atr.calculate(
                    candles,
                    signal_day=analysis_day,
                    period=risk_config.atr_period,
                )
                if evaluation.signal == Signal.BUY
                else None
            )
            held = any(position.ticker.upper() == ticker for position in state.positions)
            data_status = (
                CandidateDataStatus.INSUFFICIENT_HISTORY
                if evaluation.reason.value == "INSUFFICIENT_DATA"
                else (
                    CandidateDataStatus.READY
                    if evaluation.signal != Signal.HOLD or held
                    else CandidateDataStatus.NO_ACTION
                )
            )
            statuses.append(
                CandidateOrchestrationStatus(
                    ticker,
                    data_status,
                    latest.trading_day,
                    evaluation.signal,
                    evaluation.reason.value,
                )
            )
            if evaluation.signal != Signal.HOLD or held:
                candidates.append(
                    PortfolioCandidate(
                        ticker=ticker,
                        signal=evaluation.signal,
                        reference_price=latest.close,
                        ranking_score=score,
                        atr=atr_value,
                        sector=company.sector,
                        pre_decision_reason=(
                            PortfolioDecisionReason.INSUFFICIENT_HISTORY
                            if data_status == CandidateDataStatus.INSUFFICIENT_HISTORY
                            else None
                        ),
                    )
                )

        plan = self.decision_engine.build_plan(
            state,
            tuple(candidates),
            risk_config,
            sizing_policy=sizing_policy,
        )
        return PortfolioOrchestrationResult(
            plan=plan,
            requested_as_of_date=requested_as_of_date,
            analysis_as_of_date=analysis_day,
            statuses=tuple(statuses),
        )
