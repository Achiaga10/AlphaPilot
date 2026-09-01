from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from statistics import median
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.research_portfolio import PaperValidationRecord
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository
from alphapilot.services.live_portfolio import live_market_cache
from alphapilot.services.paper_validation import PaperValidationService, PaperValidationView

HORIZONS = (5, 10, 20)


@dataclass(frozen=True, slots=True)
class PaperTradeAnalytics:
    record: PaperValidationView
    evidence_domain: str
    completed_sessions_held: int | None
    calendar_days_held: int
    mfe_percent: Decimal | None
    mae_percent: Decimal | None
    excursion_session_count: int
    actual_exit_vs_signal_close: Decimal | None
    sessions_after_confirmed_exit_signal: int | None
    post_exit_observations: dict[str, dict[str, Any]]
    current_completed_session: date | None
    current_completed_close: Decimal | None
    current_unrealized_pnl: Decimal | None
    current_live_price: Decimal | None
    current_live_freshness: str | None


@dataclass(frozen=True, slots=True)
class PaperStrategyAnalytics:
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    open_trade_count: int
    closed_trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate_percent: Decimal | None
    average_return_percent: Decimal | None
    median_return_percent: Decimal | None
    average_winner_return_percent: Decimal | None
    average_loser_return_percent: Decimal | None
    gross_total_pnl: Decimal
    average_calendar_days_held: Decimal | None
    average_entry_adverse_slippage: Decimal | None
    average_quantity_adherence_percent: Decimal | None
    average_mfe_percent: Decimal | None
    mfe_available_count: int
    average_mae_percent: Decimal | None
    mae_available_count: int
    expectancy_return_percent: Decimal | None
    evidence_maturity: str


@dataclass(frozen=True, slots=True)
class ForwardPaperAnalytics:
    portfolio_id: UUID
    evidence_domain: str
    generated_at: datetime
    total_trade_count: int
    open_trade_count: int
    closed_trade_count: int
    wins: int
    losses: int
    breakeven: int
    gross_realized_pnl: Decimal
    win_rate_percent: Decimal | None
    average_return_percent: Decimal | None
    evidence_maturity: str
    complete_evidence_count: int
    partial_evidence_count: int
    legacy_evidence_count: int
    strategy_breakdown: tuple[PaperStrategyAnalytics, ...]
    open_trades: tuple[PaperTradeAnalytics, ...]
    closed_trades: tuple[PaperTradeAnalytics, ...]


class ForwardPaperAnalyticsService:
    """Read-only forward Paper evidence analytics; never historical backtest output."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        self.session = session
        self.records = ResearchPortfolioRepository(session)
        self.session_policy = session_policy or CompletedDailySessionPolicy()

    async def summary(
        self,
        portfolio_id: UUID,
        *,
        strategy_profile_id: str | None = None,
        ticker: str | None = None,
        status: str | None = None,
    ) -> ForwardPaperAnalytics:
        records = await self.records.list_paper_validations(portfolio_id)
        records = [
            item
            for item in records
            if (strategy_profile_id is None or item.strategy_profile_id == strategy_profile_id)
            and (ticker is None or item.ticker.upper() == ticker.upper())
            and (status is None or item.status == status)
        ]
        histories = await self._histories(records)
        trades = tuple(self._trade(item, histories.get(item.company_id, [])) for item in records)
        open_trades = tuple(item for item in trades if item.record.status == "OPEN")
        closed_trades = tuple(item for item in trades if item.record.status == "CLOSED")
        groups: dict[tuple[str | None, int | None], list[PaperTradeAnalytics]] = {}
        for trade in trades:
            key = (trade.record.strategy_profile_id, trade.record.strategy_profile_version)
            groups.setdefault(key, []).append(trade)
        breakdown = tuple(
            self._aggregate(key[0], key[1], values)
            for key, values in sorted(groups.items(), key=lambda item: str(item[0]))
        )
        closed_returns = self._values(closed_trades, "paper_gross_return_pct")
        wins, losses, breakeven = self._outcomes(closed_returns)
        views = [item.record for item in trades]
        return ForwardPaperAnalytics(
            portfolio_id,
            "FORWARD_PAPER_EVIDENCE",
            datetime.now(UTC),
            len(trades),
            len(open_trades),
            len(closed_trades),
            wins,
            losses,
            breakeven,
            sum(
                (item.record.paper_gross_pnl or Decimal("0") for item in closed_trades),
                Decimal("0"),
            ),
            self._percent(wins, len(closed_returns)),
            self._average(closed_returns),
            self._maturity(len(closed_trades)),
            sum(item.evidence_completeness == "FULL" for item in views),
            sum(item.evidence_completeness == "PARTIAL" for item in views),
            sum(item.evidence_completeness == "LEGACY" for item in views),
            breakdown,
            open_trades,
            closed_trades,
        )

    async def detail(self, portfolio_id: UUID, validation_id: UUID) -> PaperTradeAnalytics:
        record = await self.records.get_paper_validation(portfolio_id, validation_id)
        if record is None:
            raise ValueError("Paper validation not found")
        histories = await self._histories([record])
        return self._trade(record, histories.get(record.company_id, []))

    async def _histories(
        self, records: list[PaperValidationRecord]
    ) -> dict[UUID, list[DailyCandle]]:
        if not records:
            return {}
        result = await self.session.execute(
            select(DailyCandle)
            .where(
                DailyCandle.company_id.in_({item.company_id for item in records}),
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
            .order_by(DailyCandle.company_id, DailyCandle.trading_day)
        )
        output: dict[UUID, list[DailyCandle]] = {}
        for candle in result.scalars():
            output.setdefault(candle.company_id, []).append(candle)
        return output

    def _trade(
        self, record: PaperValidationRecord, candles: list[DailyCandle]
    ) -> PaperTradeAnalytics:
        view = PaperValidationService._view(record)
        entry_day = record.actual_entry_at.date()
        exit_day = record.actual_exit_at.date() if record.actual_exit_at else None
        period = [
            item
            for item in candles
            if item.trading_day > entry_day and (exit_day is None or item.trading_day < exit_day)
        ]
        entry = Decimal(record.actual_entry_price)
        mfe = (max(Decimal(item.high) for item in period) / entry - 1) * 100 if period else None
        mae = (min(Decimal(item.low) for item in period) / entry - 1) * 100 if period else None
        latest = candles[-1] if candles else None
        current_close = Decimal(latest.close) if latest else None
        live = live_market_cache.position(record.portfolio_id, record.position_id)
        signal_day = record.alphapilot_exit_triggered_on
        signal_sessions = (
            sum(signal_day < item.trading_day <= exit_day for item in candles)
            if signal_day is not None and exit_day is not None
            else None
        )
        return PaperTradeAnalytics(
            view,
            "FORWARD_PAPER_EVIDENCE",
            len(period) if candles else None,
            ((exit_day or datetime.now(UTC).date()) - entry_day).days,
            mfe,
            mae,
            len(period),
            (
                Decimal(record.actual_exit_price) - Decimal(record.alphapilot_trigger_close)
                if record.actual_exit_price is not None
                and record.alphapilot_trigger_close is not None
                else None
            ),
            signal_sessions,
            self._post_exit(record, candles),
            latest.trading_day if latest else None,
            current_close,
            (
                (current_close - entry) * Decimal(record.actual_quantity)
                if record.status == "OPEN" and current_close is not None
                else None
            ),
            live.live.last_price if live and live.live else None,
            live.live.freshness.value if live and live.live else None,
        )

    @staticmethod
    def _post_exit(
        record: PaperValidationRecord, candles: list[DailyCandle]
    ) -> dict[str, dict[str, Any]]:
        if record.actual_exit_at is None or record.actual_exit_price is None:
            return {}
        future = [item for item in candles if item.trading_day > record.actual_exit_at.date()]
        exit_price = Decimal(record.actual_exit_price)
        entry_price = Decimal(record.actual_entry_price)
        output: dict[str, dict[str, Any]] = {}
        for horizon in HORIZONS:
            window = future[:horizon]
            complete = len(window) == horizon
            output[str(horizon)] = {
                "horizon_sessions": horizon,
                "status": "COMPLETE" if complete else "INCOMPLETE",
                "available_sessions": len(window),
                "close_return_percent": (
                    str((Decimal(window[-1].close) / exit_price - 1) * 100) if complete else None
                ),
                "max_subsequent_close": (
                    str(max(Decimal(item.close) for item in window)) if complete else None
                ),
                "max_subsequent_high": (
                    str(max(Decimal(item.high) for item in window)) if complete else None
                ),
                "exit_fill_exceeded": (
                    max(Decimal(item.high) for item in window) >= exit_price if complete else None
                ),
                "entry_fill_revisited": (
                    max(Decimal(item.high) for item in window) >= entry_price if complete else None
                ),
            }
        return output

    def _aggregate(
        self,
        profile_id: str | None,
        version: int | None,
        trades: list[PaperTradeAnalytics],
    ) -> PaperStrategyAnalytics:
        closed = [item for item in trades if item.record.status == "CLOSED"]
        returns = self._values(closed, "paper_gross_return_pct")
        wins, losses, breakeven = self._outcomes(returns)
        winners = [item for item in returns if item > 0]
        losers = [item for item in returns if item < 0]
        average_winner = self._average(winners)
        average_loser = self._average(losers)
        win_rate = self._percent(wins, len(returns))
        loss_rate = Decimal(losses) / Decimal(len(returns)) if returns else None
        expectancy = (
            (win_rate / 100 * (average_winner or Decimal("0")))
            + (loss_rate * (average_loser or Decimal("0")))
            if win_rate is not None and loss_rate is not None
            else None
        )
        mfe = [item.mfe_percent for item in closed if item.mfe_percent is not None]
        mae = [item.mae_percent for item in closed if item.mae_percent is not None]
        return PaperStrategyAnalytics(
            profile_id,
            version,
            sum(item.record.status == "OPEN" for item in trades),
            len(closed),
            wins,
            losses,
            breakeven,
            win_rate,
            self._average(returns),
            Decimal(str(median(returns))) if returns else None,
            average_winner,
            average_loser,
            sum((item.record.paper_gross_pnl or Decimal("0") for item in closed), Decimal("0")),
            self._average(
                [
                    Decimal(item.record.calendar_days_held)
                    for item in closed
                    if item.record.calendar_days_held is not None
                ]
            ),
            self._average(
                [
                    item.record.entry_adverse_slippage_dollars_per_share
                    for item in trades
                    if item.record.entry_adverse_slippage_dollars_per_share is not None
                ]
            ),
            self._average(
                [
                    item.record.quantity_adherence_percent
                    for item in trades
                    if item.record.quantity_adherence_percent is not None
                ]
            ),
            self._average(mfe),
            len(mfe),
            self._average(mae),
            len(mae),
            expectancy,
            self._maturity(len(closed)),
        )

    @staticmethod
    def _values(trades: Any, field: str) -> list[Decimal]:
        return [value for item in trades if (value := getattr(item.record, field)) is not None]

    @staticmethod
    def _outcomes(values: list[Decimal]) -> tuple[int, int, int]:
        return sum(v > 0 for v in values), sum(v < 0 for v in values), sum(v == 0 for v in values)

    @staticmethod
    def _average(values: list[Decimal]) -> Decimal | None:
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else None

    @staticmethod
    def _percent(numerator: int, denominator: int) -> Decimal | None:
        return Decimal(numerator) / Decimal(denominator) * 100 if denominator else None

    @staticmethod
    def _maturity(closed_count: int) -> str:
        if closed_count == 0:
            return "NO_DATA"
        if closed_count < 5:
            return "VERY_LOW_SAMPLE"
        if closed_count < 20:
            return "LOW_SAMPLE"
        if closed_count < 50:
            return "DEVELOPING"
        return "MEANINGFUL_SAMPLE"
