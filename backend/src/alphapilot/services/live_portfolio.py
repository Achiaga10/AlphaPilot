from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.core.config import settings
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.live import (
    LiveBriefReadiness,
    LiveMarketSnapshot,
    LiveMonitoringStatus,
    LivePositionIntelligence,
    LiveQuoteFreshness,
    PortfolioLiveBrief,
    ProviderLiveSnapshot,
)
from alphapilot.market.providers.base import LiveQuoteProvider
from alphapilot.portfolio.risk import AverageTrueRangeCalculator
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.factory import create_strategy, get_strategy_stock_warmup_days
from alphapilot.strategy.indicators import calculate_ema_series, calculate_sma
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.profile import resolve_strategy_profile_identity

NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class _ProjectionCandle:
    trading_day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class LiveMarketCache:
    def __init__(self) -> None:
        self._briefs: dict[UUID, PortfolioLiveBrief] = {}

    def put(self, brief: PortfolioLiveBrief) -> None:
        self._briefs[brief.portfolio_id] = brief

    def get(self, portfolio_id: UUID) -> PortfolioLiveBrief | None:
        return self._briefs.get(portfolio_id)

    def position(self, portfolio_id: UUID, position_id: UUID) -> LivePositionIntelligence | None:
        brief = self.get(portfolio_id)
        if brief is None:
            return None
        return next((item for item in brief.positions if item.position_id == position_id), None)


live_market_cache = LiveMarketCache()


class LivePortfolioService:
    """Read-only live enrichment over completed research-portfolio facts."""

    def __init__(
        self,
        session: AsyncSession,
        provider: LiveQuoteProvider,
        *,
        cache: LiveMarketCache = live_market_cache,
        now: datetime | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.cache = cache
        self.now = now
        self.portfolios = ResearchPortfolioRepository(session)
        self.companies = CompanyRepository(session)
        self.candles = DailyCandleRepository(session)
        self.atr = AverageTrueRangeCalculator()

    async def refresh(self, portfolio_id: UUID) -> PortfolioLiveBrief:
        portfolio = await self.portfolios.get(portfolio_id)
        if portfolio is None:
            raise ValueError("Research portfolio not found")
        positions = await self.portfolios.list_open_positions(portfolio_id)
        companies = {
            item.id: item
            for item in await self.companies.get_many([p.company_id for p in positions])
        }
        tickers = [position.ticker_at_entry.upper() for position in positions]
        received_at = self._now()
        try:
            provider_snapshots = await self.provider.get_live_snapshots(tickers)
            provider_error = None
        except Exception:
            provider_snapshots = {}
            provider_error = "Live market provider is unavailable"
        completed_latest = await self.candles.get_latest_many([p.company_id for p in positions])
        starts = {
            position.company_id: (
                completed_latest[position.company_id].trading_day
                - timedelta(days=max(400, self._warmup(position)))
            )
            for position in positions
            if position.company_id in completed_latest
        }
        histories: dict[UUID, list[DailyCandle]] = {}
        if starts:
            earliest = min(starts.values())
            latest_day = max(c.trading_day for c in completed_latest.values())
            histories = await self.candles.get_histories(list(starts), earliest, latest_day)
        monitoring = {
            item.position_id: item for item in await self.portfolios.latest_monitoring(portfolio_id)
        }
        failures: list[str] = []
        output: list[LivePositionIntelligence] = []
        for position in positions:
            ticker = position.ticker_at_entry.upper()
            company = companies.get(position.company_id)
            raw = provider_snapshots.get(ticker)
            latest = completed_latest.get(position.company_id)
            if raw is None:
                failures.append(f"{ticker}: {provider_error or 'No live snapshot returned'}")
            live = self._live_snapshot(raw, position.company_id, received_at) if raw else None
            output.append(
                self._position(
                    position=position,
                    company_name=company.name if company else None,
                    candles=histories.get(position.company_id, []),
                    latest=latest,
                    live=live,
                    confirmed=monitoring.get(position.id),
                    company=company,
                )
            )
        readiness = self._readiness(output, failures)
        feed = getattr(getattr(self.provider, "feed", None), "value", "unknown")
        brief = PortfolioLiveBrief(
            portfolio.id,
            portfolio.revision,
            max(
                (item.completed_session for item in output if item.completed_session), default=None
            ),
            received_at,
            self.provider.provider_name,
            feed,
            readiness,
            tuple(output),
            tuple(failures),
            len(tickers),
            len(tickers) - len(failures),
        )
        self.cache.put(brief)
        return brief

    def _position(
        self,
        *,
        position: object,
        company_name: str | None,
        candles: list[DailyCandle],
        latest: DailyCandle | None,
        live: LiveMarketSnapshot | None,
        confirmed: object | None,
        company: object | None,
    ) -> LivePositionIntelligence:
        from alphapilot.database.models.company import Company
        from alphapilot.database.models.research_portfolio import (
            PositionMonitoringSnapshot,
            ResearchPosition,
        )

        position = cast(ResearchPosition, position)
        company = cast(Company | None, company)
        confirmed = cast(PositionMonitoringSnapshot | None, confirmed)
        closes = [Decimal(item.close) for item in candles]
        ema20 = self._last_ema(closes, 20)
        ema50 = self._last_ema(closes, 50)
        sma150 = calculate_sma(closes, 150)
        provisional_closes = [*closes, live.last_price] if live else closes
        provisional_ema20 = self._last_ema(provisional_closes, 20) if live else None
        provisional_ema50 = self._last_ema(provisional_closes, 50) if live else None
        provisional_sma150 = calculate_sma(provisional_closes, 150) if live else None
        completed_atr = (
            self.atr.calculate(candles, signal_day=latest.trading_day, period=14)
            if latest
            else None
        )
        provisional_atr = self._provisional_atr(candles, live)
        profile = None
        try:
            if position.strategy_profile_id and position.strategy_profile_version is not None:
                profile = resolve_strategy_profile_identity(
                    position.strategy_profile_id, position.strategy_profile_version
                )
        except ValueError:
            profile = None
        status, live_reason = self._live_status(
            profile.strategy if profile else None,
            live,
            provisional_ema20,
            provisional_ema50,
            provisional_sma150,
        )
        projected_signal = projected_reason = None
        if profile and live and latest and company:
            projection = _ProjectionCandle(
                live.session_date,
                live.session_open or live.last_price,
                live.session_high or live.last_price,
                live.session_low or live.last_price,
                live.last_price,
                live.volume or 0,
            )
            strategy = create_strategy(
                profile.strategy,
                exit_mode=profile.ema_exit_mode or TrendExitMode.HYBRID,
                hybrid_trend_threshold_pct=profile.hybrid_trend_threshold_pct or Decimal("2"),
                micho_entry_mode=profile.micho_entry_mode or MichoEntryMode.BOTH,
            )
            projected = strategy.evaluate(company, cast(list[DailyCandle], [*candles, projection]))
            projected_signal = projected.signal.value
            projected_reason = projected.reason.value
        previous = Decimal(latest.close) if latest else None
        change = live.last_price - previous if live and previous is not None else None
        change_pct = change / previous * Decimal("100") if change is not None and previous else None
        loss_policy = (
            "SMA150_COMPLETED_CLOSE_EXIT"
            if profile and profile.strategy == StrategyName.MICHO_150
            else "NONE"
        )
        loss_boundary = sma150 if loss_policy != "NONE" else None
        return LivePositionIntelligence(
            position.id,
            position.ticker_at_entry,
            company_name,
            position.strategy_profile_id,
            position.strategy_profile_version,
            position.quantity,
            Decimal(position.average_entry_cost),
            latest.trading_day if latest else None,
            previous,
            live,
            change,
            change_pct,
            ema20,
            provisional_ema20,
            ema50,
            provisional_ema50,
            sma150,
            provisional_sma150,
            completed_atr,
            provisional_atr,
            *self._distance(live, provisional_ema20),
            *self._distance(live, provisional_ema50),
            *self._distance(live, provisional_sma150),
            confirmed.status if confirmed else None,
            confirmed.reason if confirmed else "COMPLETED_MONITORING_UNAVAILABLE",
            status,
            live_reason,
            projected_signal,
            projected_reason,
            False,
            bool(confirmed and confirmed.status == "SELL"),
            loss_policy,
            loss_boundary,
            "COMPLETED_DAILY_CLOSE_BELOW" if loss_boundary is not None else None,
            False,
        )

    def _live_snapshot(
        self, raw: ProviderLiveSnapshot, company_id: UUID, received_at: datetime
    ) -> LiveMarketSnapshot:
        age = max(0, int((received_at - raw.quote_timestamp.astimezone(UTC)).total_seconds()))
        freshness = self._freshness(raw, received_at, age)
        coverage = (
            "Real-time IEX-only coverage; not consolidated SIP"
            if raw.feed == "iex"
            else "Consolidated SIP coverage subject to account entitlement"
        )
        return LiveMarketSnapshot(
            raw.ticker,
            company_id,
            raw.session_date,
            raw.last_price,
            raw.session_open,
            raw.session_high,
            raw.session_low,
            raw.volume,
            raw.previous_completed_close,
            raw.quote_timestamp,
            received_at,
            raw.provider,
            raw.feed,
            freshness,
            age,
            coverage,
        )

    def _freshness(
        self, raw: ProviderLiveSnapshot, received_at: datetime, age: int
    ) -> LiveQuoteFreshness:
        now_et = received_at.astimezone(NEW_YORK)
        if not (time(9, 30) <= now_et.time() <= time(16, 0)):
            return LiveQuoteFreshness.OUTSIDE_REGULAR_SESSION
        if raw.feed == "delayed_sip":
            return LiveQuoteFreshness.DELAYED
        if age > settings.LIVE_QUOTE_MAX_AGE_SECONDS:
            return LiveQuoteFreshness.STALE
        return LiveQuoteFreshness.LIVE

    @staticmethod
    def _live_status(
        strategy: StrategyName | None,
        live: LiveMarketSnapshot | None,
        ema20: Decimal | None,
        ema50: Decimal | None,
        sma150: Decimal | None,
    ) -> tuple[LiveMonitoringStatus, str]:
        if live is None or live.freshness in {LiveQuoteFreshness.STALE, LiveQuoteFreshness.UNKNOWN}:
            return LiveMonitoringStatus.UNAVAILABLE, "LIVE_DATA_UNAVAILABLE_OR_STALE"
        if strategy == StrategyName.EMA20_PULLBACK:
            if ema50 is not None and live.last_price < ema50:
                return LiveMonitoringStatus.CRITICAL_ATTENTION, "LIVE_PRICE_BELOW_PROVISIONAL_EMA50"
            if ema20 is not None and live.last_price < ema20:
                return LiveMonitoringStatus.ATTENTION, "LIVE_PRICE_BELOW_PROVISIONAL_EMA20"
            return LiveMonitoringStatus.NO_ACTION, "LIVE_PRICE_AT_OR_ABOVE_PROVISIONAL_EMA20"
        if strategy == StrategyName.MICHO_150:
            if sma150 is not None and live.last_price < sma150:
                return (
                    LiveMonitoringStatus.CRITICAL_ATTENTION,
                    "LIVE_PRICE_BELOW_PROVISIONAL_SMA150",
                )
            return LiveMonitoringStatus.NO_ACTION, "LIVE_PRICE_AT_OR_ABOVE_PROVISIONAL_SMA150"
        return LiveMonitoringStatus.UNAVAILABLE, "STRATEGY_PROFILE_UNAVAILABLE"

    def _provisional_atr(
        self, candles: list[DailyCandle], live: LiveMarketSnapshot | None
    ) -> Decimal | None:
        if not live or live.session_high is None or live.session_low is None or not candles:
            return None
        projection = _ProjectionCandle(
            live.session_date,
            live.session_open or live.last_price,
            live.session_high,
            live.session_low,
            live.last_price,
            live.volume or 0,
        )
        return self.atr.calculate(
            cast(list[DailyCandle], [*candles, projection]), signal_day=live.session_date, period=14
        )

    @staticmethod
    def _last_ema(values: list[Decimal], period: int) -> Decimal | None:
        series = calculate_ema_series(values, period)
        return series[-1] if series else None

    @staticmethod
    def _distance(
        live: LiveMarketSnapshot | None, reference: Decimal | None
    ) -> tuple[Decimal | None, Decimal | None]:
        if live is None or reference is None:
            return None, None
        distance = live.last_price - reference
        return distance, distance / reference * Decimal("100") if reference else None

    @staticmethod
    def _readiness(
        positions: list[LivePositionIntelligence], failures: list[str]
    ) -> LiveBriefReadiness:
        if failures and len(failures) == len(positions):
            return LiveBriefReadiness.UNAVAILABLE
        if failures:
            return LiveBriefReadiness.PARTIAL
        freshness = {item.live.freshness for item in positions if item.live}
        if LiveQuoteFreshness.STALE in freshness:
            return LiveBriefReadiness.STALE
        if LiveQuoteFreshness.DELAYED in freshness:
            return LiveBriefReadiness.DELAYED
        if LiveQuoteFreshness.OUTSIDE_REGULAR_SESSION in freshness:
            return LiveBriefReadiness.OUTSIDE_REGULAR_SESSION
        return LiveBriefReadiness.LIVE if positions else LiveBriefReadiness.UNAVAILABLE

    @staticmethod
    def _warmup(position: object) -> int:
        from alphapilot.database.models.research_portfolio import ResearchPosition

        item = cast(ResearchPosition, position)
        try:
            if item.strategy_profile_id and item.strategy_profile_version is not None:
                return get_strategy_stock_warmup_days(
                    resolve_strategy_profile_identity(
                        item.strategy_profile_id, item.strategy_profile_version
                    ).strategy
                )
        except ValueError:
            pass
        return 400

    def _now(self) -> datetime:
        value = self.now or datetime.now(UTC)
        return value.astimezone(UTC)
