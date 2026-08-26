from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.backtesting.ranking_features import RelativeStrength20Calculator
from alphapilot.backtesting.service import CandleHistoryService, CompanyLookupService
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecisionEngine,
    PortfolioDecisionPlan,
)
from alphapilot.portfolio.exit_guidance import build_strategy_exit_context
from alphapilot.portfolio.risk import AverageTrueRangeCalculator, PortfolioRiskConfig
from alphapilot.portfolio.sizing import (
    PortfolioDecisionReason,
    PortfolioDecisionType,
    SizingPolicyName,
)
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


class PlanReadinessStatus(StrEnum):
    READY = "READY"
    PARTIAL_DATA = "PARTIAL_DATA"
    DATA_NOT_READY = "DATA_NOT_READY"
    NO_ACTION = "NO_ACTION"


@dataclass(slots=True, frozen=True)
class CandidateOrchestrationStatus:
    ticker: str
    status: CandidateDataStatus
    data_as_of_date: date | None
    signal: Signal | None
    reason: str
    company_name: str | None = None
    sector: str | None = None
    ranking_score: Decimal | None = None
    atr: Decimal | None = None
    decision: PortfolioDecisionType | None = None
    decision_reason: PortfolioDecisionReason | None = None
    candidate_rank: int | None = None
    is_custom_tracked: bool = False
    company_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class PortfolioPlanReadiness:
    status: PlanReadinessStatus
    requested_tickers: int
    evaluated_tickers: int
    fresh_tickers: int
    stale_tickers: int
    no_data_tickers: int
    insufficient_history_tickers: int
    company_not_found_tickers: int
    buy_signals: int
    approved_buys: int
    approved_sells: int
    actionable_decisions: int
    latest_ticker_data_date: date | None
    buy_rejections_by_reason: dict[str, int]


@dataclass(slots=True, frozen=True)
class PortfolioOrchestrationResult:
    plan: PortfolioDecisionPlan
    requested_as_of_date: date
    analysis_as_of_date: date
    statuses: tuple[CandidateOrchestrationStatus, ...]
    readiness: PortfolioPlanReadiness
    evaluation_target_ticker: str | None = None


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
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        self.company_service = company_service
        self.candle_service = candle_service
        self.universe_repository = universe_repository
        self.decision_engine = decision_engine or PortfolioDecisionEngine()
        self.session_policy = session_policy or CompletedDailySessionPolicy()

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
        benchmark_candles = sorted(
            (
                item
                for item in benchmark_candles
                if item.trading_day <= requested_as_of_date
                and self.session_policy.is_complete(item.trading_day)
            ),
            key=lambda item: item.trading_day,
        )
        if not benchmark_candles:
            raise ValueError(
                "No completed stored SPY candles available on or before requested as-of date"
            )
        analysis_day = benchmark_candles[-1].trading_day
        strategy = create_strategy(
            strategy_name,
            exit_mode=exit_mode,
            hybrid_trend_threshold_pct=hybrid_trend_threshold_pct,
            micho_entry_mode=micho_entry_mode,
        )
        requested_scope = tuple(
            sorted({ticker.strip().upper() for ticker in tickers or () if ticker.strip()})
        )
        if tickers is None:
            constituents = await self.universe_repository.list_active(self.SP500_INDEX_SYMBOL)
            scope = {item.ticker.upper() for item in constituents}
        else:
            scope = set(requested_scope)
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
                (
                    item
                    for item in candles
                    if item.trading_day <= analysis_day
                    and self.session_policy.is_complete(item.trading_day)
                ),
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
                        company.name,
                        company.sector,
                        is_custom_tracked=company.is_custom_tracked,
                        company_id=company.id,
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
                        company.name,
                        company.sector,
                        is_custom_tracked=company.is_custom_tracked,
                        company_id=company.id,
                    )
                )
                continue
            evaluation = strategy.evaluate(company, candles, context)
            exit_context = build_strategy_exit_context(
                strategy=strategy_name,
                evaluation=evaluation,
                data_as_of_date=latest.trading_day,
                reference_close=latest.close,
                exit_mode=exit_mode,
                hybrid_threshold_pct=hybrid_trend_threshold_pct,
            )
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
                    company.name,
                    company.sector,
                    score,
                    atr_value,
                    is_custom_tracked=company.is_custom_tracked,
                    company_id=company.id,
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
                        exit_context=exit_context,
                    )
                )

        plan = self.decision_engine.build_plan(
            state,
            tuple(candidates),
            risk_config,
            sizing_policy=sizing_policy,
        )
        decision_by_ticker = {decision.ticker: decision for decision in plan.decisions}
        buy_rank = 0
        rank_by_ticker: dict[str, int] = {}
        for decision in plan.decisions:
            if decision.signal == Signal.BUY:
                buy_rank += 1
                rank_by_ticker[decision.ticker] = buy_rank
        statuses = [
            replace(
                status,
                decision=(
                    decision_by_ticker[status.ticker].decision
                    if status.ticker in decision_by_ticker
                    else None
                ),
                decision_reason=(
                    decision_by_ticker[status.ticker].reason
                    if status.ticker in decision_by_ticker
                    else None
                ),
                candidate_rank=rank_by_ticker.get(status.ticker),
            )
            for status in statuses
        ]
        readiness = self._readiness(tuple(statuses), plan)
        return PortfolioOrchestrationResult(
            plan=plan,
            requested_as_of_date=requested_as_of_date,
            analysis_as_of_date=analysis_day,
            statuses=tuple(statuses),
            readiness=readiness,
            evaluation_target_ticker=(requested_scope[0] if len(requested_scope) == 1 else None),
        )

    @staticmethod
    def _readiness(
        statuses: tuple[CandidateOrchestrationStatus, ...],
        plan: PortfolioDecisionPlan,
    ) -> PortfolioPlanReadiness:
        counts = {status: 0 for status in CandidateDataStatus}
        for item in statuses:
            counts[item.status] += 1
        evaluated = counts[CandidateDataStatus.READY] + counts[CandidateDataStatus.NO_ACTION]
        insufficient = counts[CandidateDataStatus.INSUFFICIENT_HISTORY]
        fresh = evaluated + insufficient
        data_issues = (
            counts[CandidateDataStatus.STALE_DATA]
            + counts[CandidateDataStatus.NO_DATA]
            + counts[CandidateDataStatus.COMPANY_NOT_FOUND]
            + insufficient
        )
        approved_buys = sum(
            decision.decision == PortfolioDecisionType.BUY for decision in plan.decisions
        )
        approved_sells = sum(
            decision.decision == PortfolioDecisionType.SELL for decision in plan.decisions
        )
        actionable = approved_buys + approved_sells
        if statuses and evaluated == 0 and data_issues > 0:
            readiness_status = PlanReadinessStatus.DATA_NOT_READY
        elif evaluated > 0 and data_issues > 0:
            readiness_status = PlanReadinessStatus.PARTIAL_DATA
        elif actionable == 0:
            readiness_status = PlanReadinessStatus.NO_ACTION
        else:
            readiness_status = PlanReadinessStatus.READY
        rejection_counts: dict[str, int] = {}
        for decision in plan.decisions:
            if decision.signal == Signal.BUY and decision.decision != PortfolioDecisionType.BUY:
                reason = decision.reason.value
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        data_dates = [item.data_as_of_date for item in statuses if item.data_as_of_date is not None]
        return PortfolioPlanReadiness(
            status=readiness_status,
            requested_tickers=len(statuses),
            evaluated_tickers=evaluated,
            fresh_tickers=fresh,
            stale_tickers=counts[CandidateDataStatus.STALE_DATA],
            no_data_tickers=counts[CandidateDataStatus.NO_DATA],
            insufficient_history_tickers=insufficient,
            company_not_found_tickers=counts[CandidateDataStatus.COMPANY_NOT_FOUND],
            buy_signals=sum(item.signal == Signal.BUY for item in statuses),
            approved_buys=approved_buys,
            approved_sells=approved_sells,
            actionable_decisions=actionable,
            latest_ticker_data_date=max(data_dates) if data_dates else None,
            buy_rejections_by_reason=dict(sorted(rejection_counts.items())),
        )
