from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import (
    PositionMonitoringSnapshot,
    ResearchPosition,
    ResearchPositionProvenance,
)
from alphapilot.portfolio.exit_guidance import build_strategy_exit_context
from alphapilot.portfolio.monitoring import (
    MonitoringReadiness,
    MonitoringReason,
    MonitoringStatus,
    PositionMonitoringResult,
    classify_monitoring,
)
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.factory import create_strategy, get_strategy_stock_warmup_days
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.profile import resolve_strategy_profile_identity


class PositionMonitoringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.portfolios = ResearchPortfolioRepository(session)
        self.companies = CompanyRepository(session)
        self.candles = DailyCandleRepository(session)

    async def monitor_portfolio(self, portfolio_id: UUID) -> list[PositionMonitoringResult]:
        results = []
        for position in await self.portfolios.list_open_positions(portfolio_id):
            results.append(await self.monitor_position(position))
        await self.session.commit()
        return results

    async def monitor_position(self, position: ResearchPosition) -> PositionMonitoringResult:
        if (
            position.provenance_status != ResearchPositionProvenance.PLAN_PROFILE.value
            or not position.strategy_profile_id
            or position.strategy_profile_version is None
        ):
            return self._unavailable(MonitoringReason.STRATEGY_PROFILE_UNKNOWN)
        try:
            profile = resolve_strategy_profile_identity(
                position.strategy_profile_id, position.strategy_profile_version
            )
        except ValueError:
            return self._unavailable(MonitoringReason.UNSUPPORTED_PROFILE_VERSION)
        company = await self.companies.get(position.company_id)
        latest = await self.candles.get_latest(position.company_id)
        benchmark = await self.companies.get_by_ticker("SPY")
        benchmark_latest = (
            await self.candles.get_latest(benchmark.id) if benchmark is not None else None
        )
        if company is None or latest is None or benchmark_latest is None:
            return self._unavailable(MonitoringReason.MARKET_DATA_UNAVAILABLE)
        if latest.trading_day != benchmark_latest.trading_day:
            return self._unavailable(MonitoringReason.MARKET_DATA_UNAVAILABLE)
        history = await self.candles.get_history(
            position.company_id,
            latest.trading_day
            - timedelta(days=max(400, get_strategy_stock_warmup_days(profile.strategy))),
            latest.trading_day,
        )
        strategy = create_strategy(
            profile.strategy,
            exit_mode=profile.ema_exit_mode or TrendExitMode.HYBRID,
            hybrid_trend_threshold_pct=profile.hybrid_trend_threshold_pct or Decimal("2"),
            micho_entry_mode=profile.micho_entry_mode or MichoEntryMode.BOTH,
        )
        evaluation = strategy.evaluate(company, history)
        context = build_strategy_exit_context(
            strategy=profile.strategy,
            evaluation=evaluation,
            data_as_of_date=latest.trading_day,
            reference_close=Decimal(latest.close),
            exit_mode=profile.ema_exit_mode or TrendExitMode.HYBRID,
            hybrid_threshold_pct=profile.hybrid_trend_threshold_pct or Decimal("2"),
        )
        try:
            status, reason = classify_monitoring(
                strategy=profile.strategy, context=context, latest_low=Decimal(latest.low)
            )
        except ValueError:
            result = self._unavailable(MonitoringReason.INSUFFICIENT_HISTORY)
            return await self._persist(position, latest.trading_day, result)
        if position.exit_triggered:
            status = MonitoringStatus.SELL
            reason = MonitoringReason(position.exit_trigger_reason or reason.value)
        elif status == MonitoringStatus.SELL:
            position.exit_triggered = True
            position.exit_triggered_on = latest.trading_day
            position.exit_trigger_reason = reason.value
        facts = {
            "close": str(latest.close),
            "low": str(latest.low),
            "ema20": str(context.ema20) if context.ema20 is not None else None,
            "ema50": str(context.ema50) if context.ema50 is not None else None,
            "ema_spread_pct": str(context.ema_spread_pct)
            if context.ema_spread_pct is not None
            else None,
            "strong_trend": context.current_exit_state.value == "BELOW_EMA20_STRONG_TREND",
            "sma150": str(context.sma150) if context.sma150 is not None else None,
            "active_exit_policy": context.exit_mode,
            "research_only_stop_candidate": profile.research_only_stop_candidate,
        }
        result = PositionMonitoringResult(
            MonitoringReadiness.READY,
            status,
            reason,
            latest.trading_day,
            Decimal(latest.close),
            facts,
            position.exit_triggered,
            position.exit_triggered_on,
            position.exit_trigger_reason,
        )
        return await self._persist(position, latest.trading_day, result)

    async def _persist(
        self, position: ResearchPosition, day: date, result: PositionMonitoringResult
    ) -> PositionMonitoringResult:
        existing = await self.portfolios.get_monitoring_snapshot(position.id, day)
        if existing is None:
            self.portfolios.add(
                PositionMonitoringSnapshot(
                    portfolio_id=position.portfolio_id,
                    position_id=position.id,
                    completed_trading_day=day,
                    readiness=result.readiness.value,
                    status=result.status.value if result.status else None,
                    reason=result.reason.value,
                    strategy_profile_id=position.strategy_profile_id,
                    strategy_profile_version=position.strategy_profile_version,
                    latest_close=result.latest_close,
                    indicator_facts=result.indicator_facts,
                    exit_triggered=result.exit_triggered,
                )
            )
        return result

    @staticmethod
    def _unavailable(reason: MonitoringReason) -> PositionMonitoringResult:
        return PositionMonitoringResult(
            MonitoringReadiness.UNAVAILABLE, None, reason, None, None, {}
        )
