from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.backtesting.ranking_features import RelativeStrength20Calculator
from alphapilot.backtesting.service import CandleHistoryService, CompanyLookupService
from alphapilot.core.config import settings
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.market.providers.base import LiveQuoteProvider
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecision,
    PortfolioDecisionEngine,
    PortfolioDecisionPlan,
)
from alphapilot.portfolio.entry_safety import (
    Ema20EntryPriceSource,
    Ema20EntrySafety,
    assess_ema20_entry_safety,
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


class BulkCompanyLookupService(CompanyLookupService, Protocol):
    async def list_companies(self) -> list[Company]: ...


class BulkCandleHistoryService(CandleHistoryService, Protocol):
    async def get_histories(
        self, company_ids: list[UUID], start: date, end: date
    ) -> dict[UUID, list[DailyCandle]]: ...


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


class BuyFunnelStage(StrEnum):
    EMA20_ENTRY_SAFETY_BLOCKED = "EMA20_ENTRY_SAFETY_BLOCKED"
    EMA20_ENTRY_REVALIDATION_UNAVAILABLE = "EMA20_ENTRY_REVALIDATION_UNAVAILABLE"
    USER_EXCLUDED = "USER_EXCLUDED"
    LOSS_CONTROL_UNAVAILABLE = "LOSS_CONTROL_UNAVAILABLE"
    PORTFOLIO_POSITION_CONSTRAINT = "PORTFOLIO_POSITION_CONSTRAINT"
    SECTOR_CONSTRAINT = "SECTOR_CONSTRAINT"
    CASH_ALLOCATION_CONSTRAINT = "CASH_ALLOCATION_CONSTRAINT"
    NEWS_AGGREGATE_UNAVAILABLE = "NEWS_AGGREGATE_UNAVAILABLE"
    NEWS_AGGREGATE_STALE = "NEWS_AGGREGATE_STALE"
    NEWS_WEAK_EVIDENCE = "NEWS_WEAK_EVIDENCE"
    TARGETED_NEWS_REVIEW_REQUIRED = "TARGETED_NEWS_REVIEW_REQUIRED"
    ATTRIBUTABLE_NEWS_UNAVAILABLE = "ATTRIBUTABLE_NEWS_UNAVAILABLE"
    GEMINI_REQUIRED_BUT_UNAVAILABLE = "GEMINI_REQUIRED_BUT_UNAVAILABLE"
    NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE = "NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE"
    OTHER = "OTHER"
    FINAL_APPROVED_BUY = "FINAL_APPROVED_BUY"


@dataclass(slots=True, frozen=True)
class BuyFunnelGroup:
    stage: BuyFunnelStage
    count: int
    tickers: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class BuyFunnelSummary:
    evaluated_tickers: int = 0
    technical_buy_signals: int = 0
    rejected_before_news: int = 0
    reached_news: int = 0
    news_advisory_only: bool = False
    final_approved_buys: int = 0
    groups: tuple[BuyFunnelGroup, ...] = ()


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
    entry_safety: Ema20EntrySafety | None = None


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
    technical_buy_signals: int = 0
    final_approved_buys: int = 0
    final_approved_sells: int = 0
    skipped_or_deferred: int = 0
    user_excluded_buys: int = 0
    buy_funnel: BuyFunnelSummary = field(default_factory=BuyFunnelSummary)


@dataclass(slots=True, frozen=True)
class PortfolioOrchestrationResult:
    plan: PortfolioDecisionPlan
    requested_as_of_date: date
    analysis_as_of_date: date
    statuses: tuple[CandidateOrchestrationStatus, ...]
    readiness: PortfolioPlanReadiness
    evaluation_target_ticker: str | None = None


@dataclass(slots=True, frozen=True)
class PortfolioMarketSnapshot:
    """One immutable universe/candle load reusable across strategy profiles."""

    requested_as_of_date: date
    analysis_as_of_date: date
    scope: tuple[str, ...]
    companies_by_ticker: dict[str, Company]
    candles_by_company_id: dict[UUID, tuple[DailyCandle, ...]]
    benchmark: Company
    benchmark_candles: tuple[DailyCandle, ...]


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
        live_quote_provider: LiveQuoteProvider | None = None,
        now: datetime | None = None,
    ) -> None:
        self.company_service = company_service
        self.candle_service = candle_service
        self.universe_repository = universe_repository
        self.decision_engine = decision_engine or PortfolioDecisionEngine()
        self.session_policy = session_policy or CompletedDailySessionPolicy()
        self.live_quote_provider = live_quote_provider
        self.now = now

    async def load_market_snapshot(
        self,
        *,
        state: CurrentPortfolioState,
        requested_as_of_date: date,
        tickers: tuple[str, ...] | None = None,
    ) -> PortfolioMarketSnapshot:
        """Bulk-load a shared market snapshot for deterministic multi-profile evaluation."""
        if not hasattr(self.company_service, "list_companies") or not hasattr(
            self.candle_service, "get_histories"
        ):
            raise TypeError("Portfolio orchestrator services do not support bulk snapshots")
        company_service = cast(BulkCompanyLookupService, self.company_service)
        candle_service = cast(BulkCandleHistoryService, self.candle_service)
        companies = await company_service.list_companies()
        companies_by_ticker = {item.ticker.upper(): item for item in companies}
        benchmark = companies_by_ticker.get(self.BENCHMARK_TICKER)
        if benchmark is None:
            raise ValueError("SPY benchmark company not found")
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
        selected_companies = [
            companies_by_ticker[ticker] for ticker in sorted(scope) if ticker in companies_by_ticker
        ]
        histories = await candle_service.get_histories(
            [benchmark.id, *(item.id for item in selected_companies)],
            requested_as_of_date - timedelta(days=self.HISTORY_DAYS),
            requested_as_of_date,
        )
        benchmark_candles = tuple(
            item
            for item in histories.get(benchmark.id, [])
            if item.trading_day <= requested_as_of_date
            and self.session_policy.is_complete(item.trading_day)
        )
        if not benchmark_candles:
            raise ValueError(
                "No completed stored SPY candles available on or before requested as-of date"
            )
        analysis_day = benchmark_candles[-1].trading_day
        return PortfolioMarketSnapshot(
            requested_as_of_date,
            analysis_day,
            tuple(sorted(scope)),
            companies_by_ticker,
            {
                company_id: tuple(
                    item
                    for item in items
                    if item.trading_day <= analysis_day
                    and self.session_policy.is_complete(item.trading_day)
                )
                for company_id, items in histories.items()
            },
            benchmark,
            benchmark_candles,
        )

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
        evaluate_existing_position_exits: bool = True,
        market_snapshot: PortfolioMarketSnapshot | None = None,
        excluded_tickers: frozenset[str] = frozenset(),
    ) -> PortfolioOrchestrationResult:
        if market_snapshot is None:
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
        else:
            if market_snapshot.requested_as_of_date != requested_as_of_date:
                raise ValueError("Market snapshot does not match requested as-of date")
            benchmark = market_snapshot.benchmark
            benchmark_candles = list(market_snapshot.benchmark_candles)
            analysis_day = market_snapshot.analysis_as_of_date
        strategy = create_strategy(
            strategy_name,
            exit_mode=exit_mode,
            hybrid_trend_threshold_pct=hybrid_trend_threshold_pct,
            micho_entry_mode=micho_entry_mode,
        )
        requested_scope = tuple(
            sorted({ticker.strip().upper() for ticker in tickers or () if ticker.strip()})
        )
        if market_snapshot is not None:
            scope = set(market_snapshot.scope)
        elif tickers is None:
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
            company = (
                market_snapshot.companies_by_ticker.get(ticker)
                if market_snapshot is not None
                else await self.company_service.get_company(ticker)
            )
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
            candles = (
                list(market_snapshot.candles_by_company_id.get(company.id, ()))
                if market_snapshot is not None
                else await self.candle_service.get_history(
                    company.id,
                    analysis_day - timedelta(days=history_days),
                    analysis_day,
                )
            )
            candles = sorted(
                (
                    item
                    for item in candles
                    if item.trading_day >= analysis_day - timedelta(days=history_days)
                    and item.trading_day <= analysis_day
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
            held = any(position.ticker.upper() == ticker for position in state.positions)
            portfolio_signal = (
                evaluation.signal if evaluate_existing_position_exits or not held else Signal.HOLD
            )
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
                if portfolio_signal == Signal.BUY
                and selection_policy == SelectionPolicyName.RELATIVE_STRENGTH_20
                else None
            )
            atr_value = (
                atr.calculate(
                    candles,
                    signal_day=analysis_day,
                    period=risk_config.atr_period,
                )
                if portfolio_signal == Signal.BUY
                else None
            )
            completed_price_timestamp = datetime.combine(
                latest.trading_day,
                time(16, 15),
                tzinfo=ZoneInfo("America/New_York"),
            ).astimezone(UTC)
            entry_safety = (
                assess_ema20_entry_safety(
                    ticker=ticker,
                    as_of=completed_price_timestamp,
                    entry_price=latest.close,
                    entry_price_source=Ema20EntryPriceSource.COMPLETED_SESSION_CLOSE,
                    entry_price_timestamp=completed_price_timestamp,
                    ema20=evaluation.ema20,
                    ema20_as_of=latest.trading_day,
                )
                if strategy_name == StrategyName.EMA20_PULLBACK and portfolio_signal == Signal.BUY
                else None
            )
            data_status = (
                CandidateDataStatus.INSUFFICIENT_HISTORY
                if evaluation.reason.value == "INSUFFICIENT_DATA"
                else (
                    CandidateDataStatus.READY
                    if portfolio_signal != Signal.HOLD or held
                    else CandidateDataStatus.NO_ACTION
                )
            )
            statuses.append(
                CandidateOrchestrationStatus(
                    ticker,
                    data_status,
                    latest.trading_day,
                    portfolio_signal,
                    evaluation.reason.value,
                    company.name,
                    company.sector,
                    score,
                    atr_value,
                    is_custom_tracked=company.is_custom_tracked,
                    company_id=company.id,
                    entry_safety=entry_safety,
                )
            )
            if portfolio_signal != Signal.HOLD or held:
                candidates.append(
                    PortfolioCandidate(
                        ticker=ticker,
                        signal=portfolio_signal,
                        reference_price=latest.close,
                        ranking_score=score,
                        atr=atr_value,
                        sector=company.sector,
                        pre_decision_reason=(
                            PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS
                            if portfolio_signal == Signal.BUY and ticker in excluded_tickers
                            else (
                                PortfolioDecisionReason.INSUFFICIENT_HISTORY
                                if data_status == CandidateDataStatus.INSUFFICIENT_HISTORY
                                else None
                            )
                        ),
                        exit_context=exit_context,
                        entry_safety=entry_safety,
                    )
                )

        candidates, statuses = await self._revalidate_live_ema_entries(
            candidates=candidates,
            statuses=statuses,
            strategy_name=strategy_name,
            requested_as_of_date=requested_as_of_date,
        )

        plan = self.decision_engine.build_plan(
            state,
            tuple(candidates),
            risk_config,
            sizing_policy=sizing_policy,
            strategy_name=strategy_name,
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

    async def _revalidate_live_ema_entries(
        self,
        *,
        candidates: list[PortfolioCandidate],
        statuses: list[CandidateOrchestrationStatus],
        strategy_name: StrategyName,
        requested_as_of_date: date,
    ) -> tuple[list[PortfolioCandidate], list[CandidateOrchestrationStatus]]:
        now = (self.now or datetime.now(UTC)).astimezone(UTC)
        now_et = now.astimezone(ZoneInfo("America/New_York"))
        during_session = time(9, 30) <= now_et.time() <= time(16, 0)
        buy_tickers = [
            item.ticker.upper()
            for item in candidates
            if item.signal == Signal.BUY and item.entry_safety is not None
        ]
        if (
            strategy_name != StrategyName.EMA20_PULLBACK
            or requested_as_of_date != now_et.date()
            or not during_session
            or not buy_tickers
        ):
            return candidates, statuses
        snapshots = {}
        if self.live_quote_provider is not None:
            try:
                snapshots = await self.live_quote_provider.get_live_snapshots(buy_tickers)
            except Exception:
                snapshots = {}
        updated: dict[str, Ema20EntrySafety] = {}
        for candidate in candidates:
            if candidate.ticker.upper() not in buy_tickers or candidate.entry_safety is None:
                continue
            raw = snapshots.get(candidate.ticker.upper())
            timestamp = raw.quote_timestamp.astimezone(UTC) if raw is not None else None
            age = (now - timestamp).total_seconds() if timestamp is not None else None
            fresh = bool(
                raw is not None
                and timestamp is not None
                and raw.session_date == now_et.date()
                and age is not None
                and 0 <= age <= settings.LIVE_QUOTE_MAX_AGE_SECONDS
                and raw.feed != "delayed_sip"
            )
            updated[candidate.ticker.upper()] = assess_ema20_entry_safety(
                ticker=candidate.ticker,
                as_of=now,
                entry_price=raw.last_price if raw is not None else None,
                entry_price_source=(
                    Ema20EntryPriceSource.ALPACA_LIVE_SNAPSHOT if raw is not None else None
                ),
                entry_price_timestamp=timestamp,
                ema20=candidate.entry_safety.ema20,
                ema20_as_of=candidate.entry_safety.ema20_as_of,
                entry_price_is_fresh=fresh,
            )
        return (
            [
                replace(
                    item,
                    reference_price=(
                        updated[item.ticker.upper()].entry_price or item.reference_price
                        if item.ticker.upper() in updated
                        else item.reference_price
                    ),
                    entry_safety=updated.get(item.ticker.upper(), item.entry_safety),
                )
                for item in candidates
            ],
            [
                replace(item, entry_safety=updated.get(item.ticker.upper(), item.entry_safety))
                for item in statuses
            ],
        )

    @staticmethod
    def final_readiness(
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
        approved_buys = sum(decision.is_approved_buy for decision in plan.decisions)
        approved_sells = sum(decision.is_approved_sell for decision in plan.decisions)
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
            if decision.signal == Signal.BUY and not decision.is_final_actionable:
                reason = (decision.terminal_reason or decision.reason).value
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        data_dates = [item.data_as_of_date for item in statuses if item.data_as_of_date is not None]
        technical_buys = sum(item.signal == Signal.BUY for item in statuses)
        skipped_or_deferred = sum(not item.is_final_actionable for item in plan.decisions)
        excluded = sum(
            item.reason == PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS
            for item in plan.decisions
        )
        buy_funnel = PortfolioDecisionOrchestrator._buy_funnel(
            statuses=tuple(statuses),
            plan=plan,
            evaluated_tickers=evaluated,
        )
        return PortfolioPlanReadiness(
            status=readiness_status,
            requested_tickers=len(statuses),
            evaluated_tickers=evaluated,
            fresh_tickers=fresh,
            stale_tickers=counts[CandidateDataStatus.STALE_DATA],
            no_data_tickers=counts[CandidateDataStatus.NO_DATA],
            insufficient_history_tickers=insufficient,
            company_not_found_tickers=counts[CandidateDataStatus.COMPANY_NOT_FOUND],
            buy_signals=technical_buys,
            approved_buys=approved_buys,
            approved_sells=approved_sells,
            actionable_decisions=actionable,
            latest_ticker_data_date=max(data_dates) if data_dates else None,
            buy_rejections_by_reason=dict(sorted(rejection_counts.items())),
            technical_buy_signals=technical_buys,
            final_approved_buys=approved_buys,
            final_approved_sells=approved_sells,
            skipped_or_deferred=skipped_or_deferred,
            user_excluded_buys=excluded,
            buy_funnel=buy_funnel,
        )

    @staticmethod
    def _buy_funnel(
        *,
        statuses: tuple[CandidateOrchestrationStatus, ...],
        plan: PortfolioDecisionPlan,
        evaluated_tickers: int,
    ) -> BuyFunnelSummary:
        decisions = {item.ticker: item for item in plan.decisions}
        grouped: dict[BuyFunnelStage, list[str]] = {}
        reached_news = 0
        for status in statuses:
            if status.signal is not Signal.BUY:
                continue
            decision = decisions.get(status.ticker)
            stage = PortfolioDecisionOrchestrator._first_buy_blocker(decision)
            grouped.setdefault(stage, []).append(status.ticker)
            if (
                decision is not None
                and not decision.news_advisory_only
                and decision.news_assessment_reason is not None
            ):
                reached_news += 1
        groups = tuple(
            BuyFunnelGroup(stage, len(tickers), tuple(sorted(tickers)))
            for stage, tickers in sorted(grouped.items(), key=lambda item: item[0].value)
        )
        technical = sum(item.signal is Signal.BUY for item in statuses)
        final = len(grouped.get(BuyFunnelStage.FINAL_APPROVED_BUY, []))
        rejected_before_news = sum(
            group.count
            for group in groups
            if group.stage
            not in {
                BuyFunnelStage.NEWS_AGGREGATE_UNAVAILABLE,
                BuyFunnelStage.NEWS_AGGREGATE_STALE,
                BuyFunnelStage.NEWS_WEAK_EVIDENCE,
                BuyFunnelStage.TARGETED_NEWS_REVIEW_REQUIRED,
                BuyFunnelStage.ATTRIBUTABLE_NEWS_UNAVAILABLE,
                BuyFunnelStage.GEMINI_REQUIRED_BUT_UNAVAILABLE,
                BuyFunnelStage.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE,
                BuyFunnelStage.FINAL_APPROVED_BUY,
            }
        )
        if sum(group.count for group in groups) != technical:
            raise AssertionError("BUY funnel must classify every technical BUY exactly once")
        return BuyFunnelSummary(
            evaluated_tickers=evaluated_tickers,
            technical_buy_signals=technical,
            rejected_before_news=rejected_before_news,
            reached_news=reached_news,
            news_advisory_only=any(item.news_advisory_only for item in plan.decisions),
            final_approved_buys=final,
            groups=groups,
        )

    @staticmethod
    def _first_buy_blocker(decision: PortfolioDecision | None) -> BuyFunnelStage:
        if decision is None:
            return BuyFunnelStage.OTHER
        reason = decision.terminal_reason or decision.reason
        if reason is PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20:
            return BuyFunnelStage.EMA20_ENTRY_SAFETY_BLOCKED
        if reason is PortfolioDecisionReason.EMA20_ENTRY_REVALIDATION_UNAVAILABLE:
            return BuyFunnelStage.EMA20_ENTRY_REVALIDATION_UNAVAILABLE
        if reason is PortfolioDecisionReason.USER_EXCLUDED_FROM_RECOMMENDATIONS:
            return BuyFunnelStage.USER_EXCLUDED
        if reason is PortfolioDecisionReason.ALREADY_HELD:
            return BuyFunnelStage.PORTFOLIO_POSITION_CONSTRAINT
        if decision.is_approved_buy:
            return BuyFunnelStage.FINAL_APPROVED_BUY
        position_reasons = {
            PortfolioDecisionReason.MAX_POSITIONS,
            PortfolioDecisionReason.RANKING_NOT_SELECTED,
        }
        if reason in position_reasons:
            return BuyFunnelStage.PORTFOLIO_POSITION_CONSTRAINT
        if reason is PortfolioDecisionReason.SECTOR_LIMIT:
            return BuyFunnelStage.SECTOR_CONSTRAINT
        if reason in {
            PortfolioDecisionReason.INSUFFICIENT_CASH,
            PortfolioDecisionReason.CASH_RESERVE,
            PortfolioDecisionReason.MAX_POSITION_WEIGHT,
            PortfolioDecisionReason.PORTFOLIO_RISK_LIMIT,
            PortfolioDecisionReason.INVALID_RISK_DISTANCE,
            PortfolioDecisionReason.INSUFFICIENT_ALLOCATION,
            PortfolioDecisionReason.INSUFFICIENT_HISTORY,
        }:
            return BuyFunnelStage.CASH_ALLOCATION_CONSTRAINT
        if not decision.loss_control_active:
            return BuyFunnelStage.LOSS_CONTROL_UNAVAILABLE
        news_stages = {
            PortfolioDecisionReason.NEWS_AGGREGATE_UNAVAILABLE: (
                BuyFunnelStage.NEWS_AGGREGATE_UNAVAILABLE
            ),
            PortfolioDecisionReason.NEWS_AGGREGATE_STALE: BuyFunnelStage.NEWS_AGGREGATE_STALE,
            PortfolioDecisionReason.NEWS_WEAK_EVIDENCE: BuyFunnelStage.NEWS_WEAK_EVIDENCE,
            PortfolioDecisionReason.TARGETED_NEWS_REVIEW_REQUIRED: (
                BuyFunnelStage.TARGETED_NEWS_REVIEW_REQUIRED
            ),
            PortfolioDecisionReason.ATTRIBUTABLE_NEWS_UNAVAILABLE: (
                BuyFunnelStage.ATTRIBUTABLE_NEWS_UNAVAILABLE
            ),
            PortfolioDecisionReason.GEMINI_REQUIRED_BUT_UNAVAILABLE: (
                BuyFunnelStage.GEMINI_REQUIRED_BUT_UNAVAILABLE
            ),
            PortfolioDecisionReason.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE: (
                BuyFunnelStage.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE
            ),
            PortfolioDecisionReason.NEWS_RISK_BLOCK: (
                BuyFunnelStage.NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE
            ),
            PortfolioDecisionReason.NEWS_ASSESSMENT_UNAVAILABLE: (
                BuyFunnelStage.NEWS_AGGREGATE_UNAVAILABLE
            ),
        }
        if reason in news_stages:
            return news_stages[reason]
        return BuyFunnelStage.OTHER

    _readiness = final_readiness
