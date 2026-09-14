from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.database.models.forward_portfolio import (
    ForwardBrokerExecutionMode,
    ForwardCycle,
    ForwardCycleStatus,
    ForwardEquityPoint,
    ForwardEvent,
    ForwardEventType,
    ForwardExecutionMode,
    ForwardOrder,
    ForwardOrderSide,
    ForwardOrderStatus,
    ForwardPortfolio,
    ForwardPortfolioStatus,
    ForwardPosition,
    ForwardPositionStatus,
    ForwardTrade,
)
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioDecision,
    PortfolioFinalAction,
    PortfolioStatePosition,
)
from alphapilot.portfolio.execution_readiness import LossControlSource
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.repositories.forward_portfolio import ForwardPortfolioRepository
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.profile import MICHO_150_V1

logger = logging.getLogger(__name__)

MONEY = Decimal("0.0001")
PCT = Decimal("100")
BASIS_POINTS = Decimal("10000")
FORWARD_SLIPPAGE_BPS = Decimal("5")
MAX_POSITIONS = 10
MICHO_LOSS_CONTROL_POLICY = "SMA150_COMPLETED_CLOSE_EXIT"
MICHO_LOSS_CONTROL_TRIGGER = "COMPLETED_DAILY_CLOSE_BELOW"


class ForwardReason(StrEnum):
    INITIALIZED = "INITIALIZED"
    USER_CONFIRMED_PAUSE = "USER_CONFIRMED_PAUSE"
    USER_CONFIRMED_RESUME = "USER_CONFIRMED_RESUME"
    CYCLE_SUCCESS = "CYCLE_SUCCESS"
    SESSION_ALREADY_PROCESSED = "SESSION_ALREADY_PROCESSED"
    PORTFOLIO_PAUSED = "PORTFOLIO_PAUSED"
    USER_EXCLUDED = "USER_EXCLUDED"
    FINAL_ACTIONABLE_BUY = "FINAL_ACTIONABLE_BUY"
    NEXT_SESSION_OPEN = "NEXT_SESSION_OPEN"
    MICHO_CLOSE_BELOW_SMA150 = "MICHO_CLOSE_BELOW_SMA150"
    ENTRY_FILLED = "ENTRY_FILLED"
    POSITION_CLOSED = "POSITION_CLOSED"
    DUPLICATE_PENDING_ENTRY = "DUPLICATE_PENDING_ENTRY"
    ALREADY_HELD = "ALREADY_HELD"
    MAX_POSITIONS = "MAX_POSITIONS"
    INSUFFICIENT_CASH_AT_FILL = "INSUFFICIENT_CASH_AT_FILL"
    LOSS_CONTROL_INVALID_AT_FILL = "LOSS_CONTROL_INVALID_AT_FILL"
    DATA_STALE = "DATA_STALE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    CYCLE_FAILED = "CYCLE_FAILED"


class ForwardPortfolioConflictError(ValueError):
    pass


class ForwardMarketDataError(RuntimeError):
    def __init__(self, event_type: ForwardEventType, ticker: str | None, detail: str) -> None:
        super().__init__(detail)
        self.event_type = event_type
        self.ticker = ticker
        self.detail = detail


@dataclass(slots=True, frozen=True)
class ForwardDecisionBatch:
    analysis_session: date
    decisions: tuple[PortfolioDecision, ...]


class ForwardDecisionProvider(Protocol):
    async def decisions(
        self,
        *,
        portfolio: ForwardPortfolio,
        positions: list[ForwardPosition],
        pending_entries: list[ForwardOrder],
        trading_session: date,
        excluded_tickers: frozenset[str],
    ) -> ForwardDecisionBatch: ...


class MichoForwardDecisionProvider:
    """Adapts the existing frozen Portfolio Plan authority to Forward state."""

    def __init__(self, orchestrator: PortfolioDecisionOrchestrator) -> None:
        self.orchestrator = orchestrator

    async def decisions(
        self,
        *,
        portfolio: ForwardPortfolio,
        positions: list[ForwardPosition],
        pending_entries: list[ForwardOrder],
        trading_session: date,
        excluded_tickers: frozenset[str],
    ) -> ForwardDecisionBatch:
        reserved = sum(
            (Decimal(item.approved_allocation) for item in pending_entries), Decimal("0")
        )
        planning_positions = [
            PortfolioStatePosition(
                ticker=item.ticker,
                shares=item.shares,
                reference_price=Decimal(item.last_close),
                cost_basis=Decimal(item.cost_basis),
                sector=None,
                modeled_risk_dollars=Decimal(item.planned_risk_dollars),
            )
            for item in positions
        ]
        for order in pending_entries:
            reference = Decimal(str(order.evidence.get("reference_price", "0")))
            if reference <= 0:
                reference = Decimal(order.approved_allocation) / Decimal(order.planned_shares)
            planning_positions.append(
                PortfolioStatePosition(
                    ticker=order.ticker,
                    shares=order.planned_shares,
                    reference_price=reference,
                    cost_basis=None,
                    sector=str(order.evidence.get("sector") or "Unclassified"),
                    modeled_risk_dollars=Decimal(order.planned_risk_dollars or 0),
                )
            )
        result = await self.orchestrator.build_plan(
            state=CurrentPortfolioState(
                cash=max(Decimal(portfolio.cash_balance) - reserved, Decimal("0")),
                positions=tuple(planning_positions),
            ),
            strategy_name=StrategyName.MICHO_150,
            selection_policy=MICHO_150_V1.recommended_selection_policy,
            sizing_policy=MICHO_150_V1.sizing_policy,
            risk_config=PortfolioRiskConfig(),
            requested_as_of_date=trading_session,
            micho_entry_mode=MichoEntryMode.BOTH,
            excluded_tickers=excluded_tickers,
        )
        return ForwardDecisionBatch(result.analysis_as_of_date, result.plan.decisions)


@dataclass(slots=True, frozen=True)
class ForwardRunResult:
    portfolio_id: UUID | None
    latest_completed_market_session: date | None
    processed_sessions: tuple[date, ...]
    skipped_sessions: tuple[date, ...]


@dataclass(slots=True, frozen=True)
class ForwardAnalytics:
    starting_equity: Decimal
    current_equity: Decimal
    cash: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    net_return_pct: Decimal
    max_drawdown_pct: Decimal
    completed_trades: int
    open_trades: int
    win_rate_pct: Decimal | None
    profit_factor: Decimal | None
    expectancy: Decimal | None
    average_winner: Decimal | None
    average_loser: Decimal | None
    worst_trade: Decimal | None
    average_holding_sessions: Decimal | None
    turnover_pct: Decimal
    friction_dollars: Decimal
    current_exposure_pct: Decimal
    average_exposure_pct: Decimal | None
    max_concurrent_positions: int
    stop_exits: int
    strategy_exits: int


class ForwardPortfolioService:
    def __init__(
        self,
        session: AsyncSession,
        decision_provider: ForwardDecisionProvider,
        *,
        session_policy: CompletedDailySessionPolicy | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.repo = ForwardPortfolioRepository(session)
        self.decision_provider = decision_provider
        self.session_policy = session_policy or CompletedDailySessionPolicy()
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    async def current(self) -> ForwardPortfolio | None:
        return await self.repo.get_current()

    async def initialize(
        self, *, initial_cash: Decimal, forward_start_session: date
    ) -> ForwardPortfolio:
        if not initial_cash.is_finite() or initial_cash <= 0:
            raise ValueError("Initial cash must be greater than zero")
        latest = await self.repo.latest_completed_session(self.session_policy.completed_through())
        if latest is not None and forward_start_session < latest:
            raise ValueError(
                "Forward start cannot precede the latest stored completed session; "
                "Forward evidence is never retrospectively backfilled"
            )
        if await self.repo.get_current() is not None:
            raise ForwardPortfolioConflictError("A live Micho Forward Portfolio already exists")
        cash = self._money(initial_cash)
        if cash <= 0:
            raise ValueError("Initial cash must be at least 0.0001 after currency precision")
        portfolio = ForwardPortfolio(
            strategy_id=MICHO_150_V1.profile_id,
            strategy_version=MICHO_150_V1.version,
            execution_mode=ForwardExecutionMode.VIRTUAL.value,
            broker_execution_mode=ForwardBrokerExecutionMode.MANUAL_EXTERNAL.value,
            status=ForwardPortfolioStatus.ACTIVE.value,
            forward_start_session=forward_start_session,
            initial_cash=cash,
            cash_balance=cash,
            equity=cash,
            realized_pnl=Decimal("0"),
            revision=0,
        )
        self.repo.add(portfolio)
        await self.repo.flush()
        self._event(
            portfolio,
            ForwardEventType.PORTFOLIO_INITIALIZED,
            trading_session=forward_start_session,
            reason=ForwardReason.INITIALIZED,
            key="portfolio:initialized",
            facts={"initial_cash": str(cash)},
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ForwardPortfolioConflictError(
                "A live Micho Forward Portfolio already exists"
            ) from exc
        return portfolio

    async def pause(self, portfolio_id: UUID, *, expected_revision: int) -> ForwardPortfolio:
        await self.repo.advisory_lock(portfolio_id)
        portfolio = await self._locked(portfolio_id, expected_revision)
        if portfolio.status == ForwardPortfolioStatus.ARCHIVED.value:
            raise ValueError("Archived Forward Portfolio cannot be paused")
        if portfolio.status == ForwardPortfolioStatus.PAUSED.value:
            await self.session.commit()
            return portfolio
        portfolio.status = ForwardPortfolioStatus.PAUSED.value
        portfolio.revision += 1
        for order in await self.repo.pending_orders(portfolio.id, side=ForwardOrderSide.ENTRY):
            order.status = ForwardOrderStatus.CANCELLED.value
            order.reason_code = ForwardReason.PORTFOLIO_PAUSED.value
            self._event(
                portfolio,
                ForwardEventType.ENTRY_CANCELLED,
                trading_session=portfolio.last_processed_session,
                ticker=order.ticker,
                reason=ForwardReason.PORTFOLIO_PAUSED,
                key=f"order:{order.id}:paused",
            )
        self._event(
            portfolio,
            ForwardEventType.PORTFOLIO_PAUSED,
            trading_session=portfolio.last_processed_session,
            reason=ForwardReason.USER_CONFIRMED_PAUSE,
            key=f"portfolio:paused:{portfolio.revision}",
        )
        await self.session.commit()
        return portfolio

    async def resume(self, portfolio_id: UUID, *, expected_revision: int) -> ForwardPortfolio:
        await self.repo.advisory_lock(portfolio_id)
        portfolio = await self._locked(portfolio_id, expected_revision)
        if portfolio.status == ForwardPortfolioStatus.ARCHIVED.value:
            raise ValueError("Archived Forward Portfolio cannot be resumed")
        if portfolio.status == ForwardPortfolioStatus.ACTIVE.value:
            await self.session.commit()
            return portfolio
        portfolio.status = ForwardPortfolioStatus.ACTIVE.value
        portfolio.revision += 1
        self._event(
            portfolio,
            ForwardEventType.PORTFOLIO_RESUMED,
            trading_session=portfolio.last_processed_session,
            reason=ForwardReason.USER_CONFIRMED_RESUME,
            key=f"portfolio:resumed:{portfolio.revision}",
        )
        await self.session.commit()
        return portfolio

    async def run_pending(self, portfolio_id: UUID | None = None) -> ForwardRunResult:
        portfolio = (
            await self.repo.get(portfolio_id)
            if portfolio_id is not None
            else await self.repo.get_current()
        )
        if portfolio is None:
            return ForwardRunResult(None, None, (), ())
        current_portfolio_id = portfolio.id
        latest = await self.repo.latest_completed_session(self.session_policy.completed_through())
        if latest is None or latest < portfolio.forward_start_session:
            await self.session.rollback()
            return ForwardRunResult(current_portfolio_id, latest, (), ())
        sessions = await self.repo.completed_sessions(
            start=portfolio.forward_start_session,
            end=latest,
            after=portfolio.last_processed_session,
        )
        await self.session.rollback()
        processed: list[date] = []
        skipped: list[date] = []
        for trading_session in sessions:
            if await self.process_session(current_portfolio_id, trading_session):
                processed.append(trading_session)
            else:
                skipped.append(trading_session)
        return ForwardRunResult(current_portfolio_id, latest, tuple(processed), tuple(skipped))

    async def process_session(self, portfolio_id: UUID, trading_session: date) -> bool:
        await self.session.rollback()
        try:
            await self.repo.advisory_lock(portfolio_id)
            portfolio = await self.repo.get(portfolio_id, for_update=True)
            if portfolio is None:
                raise ValueError("Forward Portfolio not found")
            existing = await self.repo.cycle(portfolio.id, trading_session)
            if existing is not None and existing.status in {
                ForwardCycleStatus.COMPLETED.value,
                ForwardCycleStatus.SKIPPED.value,
            }:
                skipped_key = f"cycle:{trading_session}:skipped"
                if await self.repo.event_by_key(portfolio.id, skipped_key) is None:
                    self._event(
                        portfolio,
                        ForwardEventType.CYCLE_SKIPPED,
                        trading_session=trading_session,
                        reason=ForwardReason.SESSION_ALREADY_PROCESSED,
                        key=skipped_key,
                    )
                    await self.session.commit()
                else:
                    await self.session.rollback()
                return False
            if trading_session < portfolio.forward_start_session:
                raise ValueError("Cannot process a session before the Forward start boundary")
            if portfolio.status == ForwardPortfolioStatus.ARCHIVED.value:
                await self.session.rollback()
                return False
            now = self.now_provider()
            cycle = existing or ForwardCycle(
                portfolio_id=portfolio.id,
                trading_session=trading_session,
                status=ForwardCycleStatus.RUNNING.value,
                started_at=now,
                audit_facts={},
            )
            cycle.status = ForwardCycleStatus.RUNNING.value
            cycle.started_at = now
            cycle.completed_at = None
            cycle.error_code = None
            if existing is None:
                self.repo.add(cycle)
            self._event(
                portfolio,
                ForwardEventType.CYCLE_STARTED,
                trading_session=trading_session,
                reason=ForwardReason.CYCLE_SUCCESS,
                key=f"cycle:{trading_session}:started",
            )
            opening_exits = await self._fill_pending_exits(portfolio, trading_session)
            opening_entries = await self._fill_pending_entries(portfolio, trading_session)
            positions = await self.repo.open_positions(portfolio.id)
            await self._mark_positions(portfolio, positions, trading_session)
            positions = await self.repo.open_positions(portfolio.id)
            pending_entries = await self.repo.pending_orders(
                portfolio.id, side=ForwardOrderSide.ENTRY
            )
            excluded = await self.repo.excluded_tickers()
            decision_batch = await self.decision_provider.decisions(
                portfolio=portfolio,
                positions=positions,
                pending_entries=pending_entries,
                trading_session=trading_session,
                excluded_tickers=excluded,
            )
            if decision_batch.analysis_session != trading_session:
                raise ForwardMarketDataError(
                    ForwardEventType.DATA_STALE,
                    None,
                    f"analysis_session={decision_batch.analysis_session}",
                )
            await self._apply_decisions(
                portfolio, trading_session, decision_batch.decisions, excluded_tickers=excluded
            )
            positions = await self.repo.open_positions(portfolio.id)
            market_value, unrealized = await self._mark_positions(
                portfolio, positions, trading_session
            )
            equity = self._money(Decimal(portfolio.cash_balance) + market_value)
            portfolio.equity = equity
            portfolio.last_processed_session = trading_session
            portfolio.last_successful_cycle = now
            portfolio.last_error = None
            portfolio.revision += 1
            exposure = market_value / equity * PCT if equity > 0 else Decimal("0")
            self.repo.add(
                ForwardEquityPoint(
                    portfolio_id=portfolio.id,
                    trading_session=trading_session,
                    cash=self._money(Decimal(portfolio.cash_balance)),
                    positions_market_value=self._money(market_value),
                    equity=equity,
                    realized_pnl=self._money(Decimal(portfolio.realized_pnl)),
                    unrealized_pnl=self._money(unrealized),
                    open_position_count=len(positions),
                    exposure_pct=self._pct(exposure),
                )
            )
            cycle.status = ForwardCycleStatus.COMPLETED.value
            cycle.completed_at = self.now_provider()
            cycle.audit_facts = {
                "opening_exits": opening_exits,
                "opening_entries": opening_entries,
                "open_positions": len(positions),
                "cash": str(portfolio.cash_balance),
                "equity": str(equity),
            }
            self._event(
                portfolio,
                ForwardEventType.CYCLE_COMPLETED,
                trading_session=trading_session,
                reason=ForwardReason.CYCLE_SUCCESS,
                key=f"cycle:{trading_session}:completed",
                facts=cycle.audit_facts,
            )
            await self.session.commit()
            logger.info(
                "Forward Portfolio cycle completed",
                extra={
                    "portfolio_id": str(portfolio.id),
                    "cycle_session": str(trading_session),
                    "strategy_id": portfolio.strategy_id,
                    "event": ForwardEventType.CYCLE_COMPLETED.value,
                    "reason": ForwardReason.CYCLE_SUCCESS.value,
                },
            )
            return True
        except Exception as exc:
            await self.session.rollback()
            await self._record_cycle_failure(
                portfolio_id,
                trading_session,
                type(exc).__name__,
                data_error=exc if isinstance(exc, ForwardMarketDataError) else None,
            )
            raise

    async def _fill_pending_exits(self, portfolio: ForwardPortfolio, trading_session: date) -> int:
        orders = await self.repo.pending_orders(portfolio.id, side=ForwardOrderSide.EXIT)
        positions = {item.id: item for item in await self.repo.open_positions(portfolio.id)}
        filled = 0
        for order in orders:
            if order.source_signal_session >= trading_session:
                continue
            order.planned_execution_session = order.planned_execution_session or trading_session
            position = positions.get(order.position_id) if order.position_id is not None else None
            if position is None:
                order.status = ForwardOrderStatus.CANCELLED.value
                order.reason_code = ForwardReason.POSITION_CLOSED.value
                continue
            candle = await self.repo.candle(order.company_id, trading_session)
            if candle is None:
                raise ForwardMarketDataError(
                    ForwardEventType.DATA_UNAVAILABLE,
                    order.ticker,
                    "EXIT_OPEN_MISSING",
                )
            raw = Decimal(candle.open)
            modeled = self._sell_fill(raw)
            shares = position.shares
            proceeds = self._money(modeled * Decimal(shares))
            friction = self._money((raw - modeled) * Decimal(shares))
            gross = self._money((raw - Decimal(position.raw_entry_price)) * Decimal(shares))
            net = self._money(proceeds - Decimal(position.cost_basis))
            entry_order = await self._entry_order(position)
            portfolio.cash_balance = self._money(Decimal(portfolio.cash_balance) + proceeds)
            portfolio.realized_pnl = self._money(Decimal(portfolio.realized_pnl) + net)
            order.status = ForwardOrderStatus.FILLED.value
            order.actual_execution_session = trading_session
            order.filled_shares = shares
            order.raw_fill_price = raw
            order.modeled_fill_price = modeled
            order.friction_dollars = friction
            position.status = ForwardPositionStatus.CLOSED.value
            position.closed_session = trading_session
            position.management_status = "CLOSED"
            sessions = await self.repo.completed_sessions(
                start=position.entry_session, end=trading_session
            )
            self.repo.add(
                ForwardTrade(
                    portfolio_id=portfolio.id,
                    position_id=position.id,
                    company_id=position.company_id,
                    ticker=position.ticker,
                    strategy_id=portfolio.strategy_id,
                    strategy_version=portfolio.strategy_version,
                    signal_session=position.signal_session,
                    entry_session=position.entry_session,
                    raw_entry_price=position.raw_entry_price,
                    modeled_entry_price=position.modeled_entry_price,
                    entry_friction=position.entry_friction,
                    approved_allocation=entry_order.approved_allocation,
                    shares=shares,
                    loss_control_policy=position.loss_control_policy,
                    initial_loss_control_boundary=Decimal(entry_order.loss_control_boundary or 0),
                    loss_control_trigger=position.loss_control_trigger,
                    loss_control_source=position.loss_control_source,
                    risk_per_share=position.risk_per_share,
                    planned_risk_dollars=position.planned_risk_dollars,
                    entry_evidence=dict(entry_order.evidence),
                    exit_signal_session=order.source_signal_session,
                    exit_session=trading_session,
                    raw_exit_price=raw,
                    modeled_exit_price=modeled,
                    exit_friction=friction,
                    exit_reason=order.reason_code,
                    gross_pnl=gross,
                    net_pnl=net,
                    return_pct=self._pct(
                        net / Decimal(position.cost_basis) * PCT
                        if position.cost_basis
                        else Decimal("0")
                    ),
                    holding_sessions=len(sessions),
                    holding_calendar_days=(trading_session - position.entry_session).days,
                )
            )
            for event_type, reason in (
                (ForwardEventType.EXIT_FILLED, ForwardReason.NEXT_SESSION_OPEN),
                (ForwardEventType.POSITION_CLOSED, ForwardReason.POSITION_CLOSED),
            ):
                self._event(
                    portfolio,
                    event_type,
                    trading_session=trading_session,
                    ticker=order.ticker,
                    reason=reason,
                    key=f"order:{order.id}:{event_type.value}",
                    facts={"shares": shares, "raw_price": str(raw), "fill_price": str(modeled)},
                )
            filled += 1
        return filled

    async def _fill_pending_entries(
        self, portfolio: ForwardPortfolio, trading_session: date
    ) -> int:
        if portfolio.status != ForwardPortfolioStatus.ACTIVE.value:
            return 0
        orders = await self.repo.pending_orders(portfolio.id, side=ForwardOrderSide.ENTRY)
        positions = await self.repo.open_positions(portfolio.id)
        open_company_ids = {item.company_id for item in positions}
        filled = 0
        for order in orders:
            if order.source_signal_session >= trading_session:
                continue
            order.planned_execution_session = order.planned_execution_session or trading_session
            if order.company_id in open_company_ids:
                self._cancel_entry(portfolio, order, trading_session, ForwardReason.ALREADY_HELD)
                continue
            if len(open_company_ids) >= MAX_POSITIONS:
                self._cancel_entry(portfolio, order, trading_session, ForwardReason.MAX_POSITIONS)
                continue
            candle = await self.repo.candle(order.company_id, trading_session)
            if candle is None:
                raise ForwardMarketDataError(
                    ForwardEventType.DATA_UNAVAILABLE,
                    order.ticker,
                    "ENTRY_OPEN_MISSING",
                )
            raw = Decimal(candle.open)
            modeled = self._buy_fill(raw)
            allocation_shares = int(
                (Decimal(order.approved_allocation) / modeled).to_integral_value(
                    rounding=ROUND_FLOOR
                )
            )
            cash_shares = int(
                (Decimal(portfolio.cash_balance) / modeled).to_integral_value(rounding=ROUND_FLOOR)
            )
            shares = min(order.planned_shares, allocation_shares, cash_shares)
            if shares <= 0:
                self._cancel_entry(
                    portfolio, order, trading_session, ForwardReason.INSUFFICIENT_CASH_AT_FILL
                )
                continue
            boundary = Decimal(order.loss_control_boundary or 0)
            if boundary <= 0:
                self._cancel_entry(
                    portfolio, order, trading_session, ForwardReason.LOSS_CONTROL_INVALID_AT_FILL
                )
                continue
            cost = self._money(modeled * Decimal(shares))
            friction = self._money((modeled - raw) * Decimal(shares))
            risk_per_share = self._money(Decimal(order.risk_per_share or 0))
            risk_dollars = self._money(risk_per_share * Decimal(shares))
            portfolio.cash_balance = self._money(Decimal(portfolio.cash_balance) - cost)
            if portfolio.cash_balance < 0:
                raise AssertionError("Forward cash cannot become negative")
            position = ForwardPosition(
                portfolio_id=portfolio.id,
                company_id=order.company_id,
                entry_order_id=order.id,
                ticker=order.ticker,
                status=ForwardPositionStatus.OPEN.value,
                shares=shares,
                signal_session=order.source_signal_session,
                entry_session=trading_session,
                raw_entry_price=raw,
                modeled_entry_price=modeled,
                entry_friction=friction,
                cost_basis=cost,
                last_mark_session=trading_session,
                last_close=Decimal(candle.close),
                market_value=self._money(Decimal(candle.close) * Decimal(shares)),
                unrealized_pnl=self._money(Decimal(candle.close) * Decimal(shares) - cost),
                unrealized_return_pct=self._pct(
                    (Decimal(candle.close) * Decimal(shares) - cost) / cost * PCT
                ),
                loss_control_policy=order.loss_control_policy,
                loss_control_boundary=boundary,
                loss_control_trigger=order.loss_control_trigger or MICHO_LOSS_CONTROL_TRIGGER,
                loss_control_source=LossControlSource.APPROVED_SYSTEM_POLICY.value,
                risk_per_share=risk_per_share,
                planned_risk_dollars=risk_dollars,
                holding_sessions=1,
                holding_calendar_days=0,
                management_status="OPEN",
            )
            self.repo.add(position)
            await self.repo.flush()
            order.position_id = position.id
            order.status = ForwardOrderStatus.FILLED.value
            order.actual_execution_session = trading_session
            order.filled_shares = shares
            order.raw_fill_price = raw
            order.modeled_fill_price = modeled
            order.friction_dollars = friction
            order.reason_code = ForwardReason.ENTRY_FILLED.value
            for event_type in (ForwardEventType.ENTRY_FILLED, ForwardEventType.POSITION_OPENED):
                self._event(
                    portfolio,
                    event_type,
                    trading_session=trading_session,
                    ticker=order.ticker,
                    reason=ForwardReason.ENTRY_FILLED,
                    key=f"order:{order.id}:{event_type.value}",
                    facts={
                        "shares": shares,
                        "raw_price": str(raw),
                        "fill_price": str(modeled),
                        "cash_after": str(portfolio.cash_balance),
                    },
                )
            open_company_ids.add(order.company_id)
            filled += 1
        return filled

    async def _apply_decisions(
        self,
        portfolio: ForwardPortfolio,
        trading_session: date,
        decisions: tuple[PortfolioDecision, ...],
        *,
        excluded_tickers: frozenset[str],
    ) -> None:
        positions = {item.ticker: item for item in await self.repo.open_positions(portfolio.id)}
        pending_entries = {
            item.ticker: item
            for item in await self.repo.pending_orders(portfolio.id, side=ForwardOrderSide.ENTRY)
        }
        pending_exits = {
            item.ticker: item
            for item in await self.repo.pending_orders(portfolio.id, side=ForwardOrderSide.EXIT)
        }
        for rank, decision in enumerate(decisions, start=1):
            position = positions.get(decision.ticker)
            if position is not None and decision.exit_context is not None:
                boundary = decision.exit_context.sma150
                if boundary is not None and boundary > 0:
                    position.loss_control_boundary = boundary
            if decision.is_approved_sell and position is not None:
                if decision.ticker in pending_exits:
                    continue
                position.exit_signal_session = trading_session
                position.management_status = "EXIT_PENDING"
                order = ForwardOrder(
                    portfolio_id=portfolio.id,
                    company_id=position.company_id,
                    position_id=position.id,
                    ticker=position.ticker,
                    side=ForwardOrderSide.EXIT.value,
                    status=ForwardOrderStatus.PENDING.value,
                    source_signal_session=trading_session,
                    approved_allocation=Decimal("0"),
                    planned_shares=position.shares,
                    friction_bps=FORWARD_SLIPPAGE_BPS,
                    reason_code=ForwardReason.MICHO_CLOSE_BELOW_SMA150.value,
                    strategy_id=portfolio.strategy_id,
                    strategy_version=portfolio.strategy_version,
                    loss_control_policy=position.loss_control_policy,
                    loss_control_boundary=position.loss_control_boundary,
                    loss_control_trigger=position.loss_control_trigger,
                    risk_per_share=position.risk_per_share,
                    planned_risk_dollars=position.planned_risk_dollars,
                    evidence={
                        "initial_loss_control_boundary": str(
                            (await self._entry_order(position)).loss_control_boundary
                        ),
                        "signal_close": str(decision.reference_price),
                        "signal_sma150": str(position.loss_control_boundary),
                    },
                )
                self.repo.add(order)
                await self.repo.flush()
                for event_type in (
                    ForwardEventType.STRATEGY_EXIT_SIGNALLED,
                    ForwardEventType.EXIT_PLANNED,
                ):
                    self._event(
                        portfolio,
                        event_type,
                        trading_session=trading_session,
                        ticker=position.ticker,
                        reason=ForwardReason.MICHO_CLOSE_BELOW_SMA150,
                        key=f"order:{order.id}:{event_type.value}",
                        facts={
                            "close": str(decision.reference_price),
                            "sma150": str(position.loss_control_boundary),
                        },
                    )
                continue
            if not decision.is_approved_buy or not decision.forward_execution_eligible:
                continue
            if portfolio.status != ForwardPortfolioStatus.ACTIVE.value:
                self._signal_skipped(
                    portfolio, trading_session, decision.ticker, ForwardReason.PORTFOLIO_PAUSED
                )
                continue
            if decision.ticker in excluded_tickers:
                self._signal_skipped(
                    portfolio, trading_session, decision.ticker, ForwardReason.USER_EXCLUDED
                )
                continue
            if decision.ticker in positions:
                self._signal_skipped(
                    portfolio, trading_session, decision.ticker, ForwardReason.ALREADY_HELD
                )
                continue
            if decision.ticker in pending_entries:
                self._signal_skipped(
                    portfolio,
                    trading_session,
                    decision.ticker,
                    ForwardReason.DUPLICATE_PENDING_ENTRY,
                )
                continue
            if len(positions) + len(pending_entries) >= MAX_POSITIONS:
                self._signal_skipped(
                    portfolio, trading_session, decision.ticker, ForwardReason.MAX_POSITIONS
                )
                continue
            boundary = decision.loss_control_boundary_price
            if (
                boundary is None
                or not decision.loss_control_active
                or decision.loss_control_source is not LossControlSource.APPROVED_SYSTEM_POLICY
                or decision.loss_control_policy != MICHO_LOSS_CONTROL_POLICY
            ):
                continue
            company = await self.repo.company(decision.ticker)
            if company is None:
                self._data_unavailable(
                    portfolio, trading_session, decision.ticker, "COMPANY_NOT_FOUND"
                )
                continue
            risk_per_share = decision.reference_price - boundary
            if risk_per_share <= 0 or decision.proposed_shares <= 0:
                continue
            order = ForwardOrder(
                portfolio_id=portfolio.id,
                company_id=company.id,
                ticker=decision.ticker,
                side=ForwardOrderSide.ENTRY.value,
                status=ForwardOrderStatus.PENDING.value,
                source_signal_session=trading_session,
                approved_allocation=self._money(decision.target_allocation_dollars),
                planned_shares=decision.proposed_shares,
                friction_bps=FORWARD_SLIPPAGE_BPS,
                reason_code=ForwardReason.FINAL_ACTIONABLE_BUY.value,
                strategy_id=portfolio.strategy_id,
                strategy_version=portfolio.strategy_version,
                ranking_score=decision.ranking_score,
                ranking_position=rank,
                loss_control_policy=decision.loss_control_policy,
                loss_control_boundary=boundary,
                loss_control_trigger=decision.loss_control_trigger,
                risk_per_share=self._money(risk_per_share),
                planned_risk_dollars=self._money(decision.modeled_position_risk_dollars),
                planned_risk_pct=(
                    self._pct(
                        decision.modeled_position_risk_dollars / Decimal(portfolio.equity) * PCT
                    )
                    if portfolio.equity
                    else None
                ),
                evidence={
                    "reference_price": str(decision.reference_price),
                    "sector": decision.sector,
                    "final_action": PortfolioFinalAction.BUY.value,
                    "is_final_actionable": True,
                    "selection_policy": SelectionPolicyName.RELATIVE_STRENGTH_20.value,
                    "ranking_score": str(decision.ranking_score)
                    if decision.ranking_score is not None
                    else None,
                },
            )
            self.repo.add(order)
            await self.repo.flush()
            pending_entries[decision.ticker] = order
            self._event(
                portfolio,
                ForwardEventType.SIGNAL_APPROVED,
                trading_session=trading_session,
                ticker=decision.ticker,
                reason=ForwardReason.FINAL_ACTIONABLE_BUY,
                key=f"order:{order.id}:approved",
                facts={
                    "allocation": str(order.approved_allocation),
                    "shares": order.planned_shares,
                },
            )
            self._event(
                portfolio,
                ForwardEventType.ENTRY_PLANNED,
                trading_session=trading_session,
                ticker=decision.ticker,
                reason=ForwardReason.NEXT_SESSION_OPEN,
                key=f"order:{order.id}:planned",
                facts={"loss_control_boundary": str(boundary)},
            )

    async def _entry_order(self, position: ForwardPosition) -> ForwardOrder:
        orders = await self.repo.orders(position.portfolio_id)
        order = next((item for item in orders if item.id == position.entry_order_id), None)
        if order is None:
            raise AssertionError("Forward position entry provenance is missing")
        return order

    async def _mark_positions(
        self,
        portfolio: ForwardPortfolio,
        positions: list[ForwardPosition],
        trading_session: date,
    ) -> tuple[Decimal, Decimal]:
        market_value = Decimal("0")
        unrealized = Decimal("0")
        for position in positions:
            candle = await self.repo.candle(position.company_id, trading_session)
            if candle is not None:
                position.last_mark_session = trading_session
                position.last_close = Decimal(candle.close)
                position.market_value = self._money(
                    Decimal(candle.close) * Decimal(position.shares)
                )
                position.unrealized_pnl = self._money(
                    Decimal(position.market_value) - Decimal(position.cost_basis)
                )
                position.unrealized_return_pct = self._pct(
                    Decimal(position.unrealized_pnl) / Decimal(position.cost_basis) * PCT
                )
                position.holding_sessions = len(
                    await self.repo.completed_sessions(
                        start=position.entry_session, end=trading_session
                    )
                )
                position.holding_calendar_days = (trading_session - position.entry_session).days
            else:
                raise ForwardMarketDataError(
                    ForwardEventType.DATA_UNAVAILABLE,
                    position.ticker,
                    "POSITION_MARK_MISSING",
                )
            market_value += Decimal(position.market_value)
            unrealized += Decimal(position.unrealized_pnl)
        return self._money(market_value), self._money(unrealized)

    def _cancel_entry(
        self,
        portfolio: ForwardPortfolio,
        order: ForwardOrder,
        trading_session: date,
        reason: ForwardReason,
    ) -> None:
        order.status = ForwardOrderStatus.CANCELLED.value
        order.reason_code = reason.value
        self._event(
            portfolio,
            ForwardEventType.ENTRY_CANCELLED,
            trading_session=trading_session,
            ticker=order.ticker,
            reason=reason,
            key=f"order:{order.id}:cancelled",
        )

    def _data_unavailable(
        self, portfolio: ForwardPortfolio, trading_session: date, ticker: str, detail: str
    ) -> None:
        self._event(
            portfolio,
            ForwardEventType.DATA_UNAVAILABLE,
            trading_session=trading_session,
            ticker=ticker,
            reason=ForwardReason.DATA_UNAVAILABLE,
            key=f"data:{trading_session}:{ticker}:{detail}",
            facts={"detail": detail},
        )

    def _signal_skipped(
        self,
        portfolio: ForwardPortfolio,
        trading_session: date,
        ticker: str,
        reason: ForwardReason,
    ) -> None:
        self._event(
            portfolio,
            ForwardEventType.SIGNAL_SKIPPED,
            trading_session=trading_session,
            ticker=ticker,
            reason=reason,
            key=f"signal:{trading_session}:{ticker}:skipped",
        )

    async def _record_cycle_failure(
        self,
        portfolio_id: UUID,
        trading_session: date,
        error_code: str,
        *,
        data_error: ForwardMarketDataError | None = None,
    ) -> None:
        await self.repo.advisory_lock(portfolio_id)
        portfolio = await self.repo.get(portfolio_id, for_update=True)
        if portfolio is None:
            await self.session.rollback()
            return
        if trading_session < portfolio.forward_start_session:
            await self.session.rollback()
            return
        cycle = await self.repo.cycle(portfolio_id, trading_session)
        if cycle is None:
            cycle = ForwardCycle(
                portfolio_id=portfolio_id,
                trading_session=trading_session,
                status=ForwardCycleStatus.FAILED.value,
                started_at=self.now_provider(),
                completed_at=self.now_provider(),
                error_code=error_code,
                audit_facts={},
            )
            self.repo.add(cycle)
        else:
            cycle.status = ForwardCycleStatus.FAILED.value
            cycle.completed_at = self.now_provider()
            cycle.error_code = error_code
        portfolio.last_error = "Forward cycle failed. Review structured server logs."
        failure_key = f"cycle:{trading_session}:failed"
        if await self.repo.event_by_key(portfolio_id, failure_key) is None:
            self._event(
                portfolio,
                ForwardEventType.CYCLE_FAILED,
                trading_session=trading_session,
                reason=ForwardReason.CYCLE_FAILED,
                key=failure_key,
                facts={"error_code": error_code},
            )
        if data_error is not None:
            event_key = (
                f"data:{trading_session}:{data_error.ticker or 'PORTFOLIO'}:{data_error.detail}"
            )
            if await self.repo.event_by_key(portfolio_id, event_key) is None:
                self._event(
                    portfolio,
                    data_error.event_type,
                    trading_session=trading_session,
                    ticker=data_error.ticker,
                    reason=(
                        ForwardReason.DATA_STALE
                        if data_error.event_type is ForwardEventType.DATA_STALE
                        else ForwardReason.DATA_UNAVAILABLE
                    ),
                    key=event_key,
                    facts={"detail": data_error.detail},
                )
        await self.session.commit()
        logger.exception(
            "Forward Portfolio cycle failed",
            extra={
                "portfolio_id": str(portfolio_id),
                "cycle_session": str(trading_session),
                "strategy_id": portfolio.strategy_id,
                "event": "CYCLE_FAILED",
                "reason": error_code,
            },
        )

    async def _locked(self, portfolio_id: UUID, revision: int) -> ForwardPortfolio:
        portfolio = await self.repo.get(portfolio_id, for_update=True)
        if portfolio is None:
            raise ValueError("Forward Portfolio not found")
        if portfolio.revision != revision:
            raise ForwardPortfolioConflictError(
                "Forward Portfolio revision is stale: "
                f"expected {portfolio.revision}, received {revision}"
            )
        return portfolio

    def _event(
        self,
        portfolio: ForwardPortfolio,
        event_type: ForwardEventType,
        *,
        trading_session: date | None,
        reason: ForwardReason,
        key: str,
        ticker: str | None = None,
        facts: dict[str, object] | None = None,
    ) -> None:
        self.repo.add(
            ForwardEvent(
                portfolio_id=portfolio.id,
                event_type=event_type.value,
                trading_session=trading_session,
                ticker=ticker,
                strategy_id=portfolio.strategy_id,
                reason_code=reason.value,
                idempotency_key=key,
                numeric_provenance=facts or {},
                created_at=self.now_provider(),
            )
        )

    async def positions(self, portfolio_id: UUID) -> list[ForwardPosition]:
        return await self.repo.positions(portfolio_id)

    async def orders(self, portfolio_id: UUID) -> list[ForwardOrder]:
        return await self.repo.orders(portfolio_id)

    async def trades(self, portfolio_id: UUID) -> list[ForwardTrade]:
        return await self.repo.trades(portfolio_id)

    async def events(self, portfolio_id: UUID, *, limit: int = 200) -> list[ForwardEvent]:
        return await self.repo.events(portfolio_id, limit=limit)

    async def analytics(self, portfolio_id: UUID) -> ForwardAnalytics:
        portfolio = await self.repo.get(portfolio_id)
        if portfolio is None:
            raise ValueError("Forward Portfolio not found")
        positions = await self.repo.open_positions(portfolio_id)
        trades = await self.repo.trades(portfolio_id)
        points = await self.repo.equity_points(portfolio_id)
        wins = [Decimal(item.net_pnl) for item in trades if item.net_pnl > 0]
        losses = [Decimal(item.net_pnl) for item in trades if item.net_pnl < 0]
        gross_profit = sum(wins, Decimal("0"))
        gross_loss = abs(sum(losses, Decimal("0")))
        peak = Decimal(portfolio.initial_cash)
        max_drawdown = Decimal("0")
        for point in points:
            equity = Decimal(point.equity)
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak * PCT)
        market_value = sum((Decimal(item.market_value) for item in positions), Decimal("0"))
        unrealized = sum((Decimal(item.unrealized_pnl) for item in positions), Decimal("0"))
        pnl_values = [Decimal(item.net_pnl) for item in trades]
        entry_turnover = sum(
            (Decimal(item.modeled_entry_price) * Decimal(item.shares) for item in trades),
            Decimal("0"),
        ) + sum((Decimal(item.cost_basis) for item in positions), Decimal("0"))
        exit_turnover = sum(
            (Decimal(item.modeled_exit_price) * Decimal(item.shares) for item in trades),
            Decimal("0"),
        )
        friction = sum(
            (Decimal(item.entry_friction) + Decimal(item.exit_friction) for item in trades),
            Decimal("0"),
        ) + sum((Decimal(item.entry_friction) for item in positions), Decimal("0"))
        return ForwardAnalytics(
            starting_equity=Decimal(portfolio.initial_cash),
            current_equity=Decimal(portfolio.equity),
            cash=Decimal(portfolio.cash_balance),
            market_value=self._money(market_value),
            realized_pnl=Decimal(portfolio.realized_pnl),
            unrealized_pnl=self._money(unrealized),
            total_pnl=self._money(Decimal(portfolio.equity) - Decimal(portfolio.initial_cash)),
            net_return_pct=self._pct(
                (Decimal(portfolio.equity) / Decimal(portfolio.initial_cash) - Decimal("1")) * PCT
            ),
            max_drawdown_pct=self._pct(max_drawdown),
            completed_trades=len(trades),
            open_trades=len(positions),
            win_rate_pct=(
                self._pct(Decimal(len(wins)) / Decimal(len(trades)) * PCT) if trades else None
            ),
            profit_factor=(self._pct(gross_profit / gross_loss) if gross_loss > 0 else None),
            expectancy=(
                self._money(sum(pnl_values, Decimal("0")) / Decimal(len(pnl_values)))
                if pnl_values
                else None
            ),
            average_winner=(self._money(gross_profit / Decimal(len(wins))) if wins else None),
            average_loser=(
                self._money(sum(losses, Decimal("0")) / Decimal(len(losses))) if losses else None
            ),
            worst_trade=(self._money(min(pnl_values)) if pnl_values else None),
            average_holding_sessions=(
                self._pct(
                    Decimal(sum(item.holding_sessions for item in trades)) / Decimal(len(trades))
                )
                if trades
                else None
            ),
            turnover_pct=self._pct(
                (entry_turnover + exit_turnover) / Decimal(portfolio.initial_cash) * PCT
            ),
            friction_dollars=self._money(friction),
            current_exposure_pct=self._pct(
                market_value / Decimal(portfolio.equity) * PCT if portfolio.equity else Decimal("0")
            ),
            average_exposure_pct=(
                self._pct(
                    sum((Decimal(item.exposure_pct) for item in points), Decimal("0"))
                    / Decimal(len(points))
                )
                if points
                else None
            ),
            max_concurrent_positions=max(
                (item.open_position_count for item in points), default=len(positions)
            ),
            stop_exits=sum("STOP" in item.exit_reason for item in trades),
            strategy_exits=sum(
                item.exit_reason == ForwardReason.MICHO_CLOSE_BELOW_SMA150.value for item in trades
            ),
        )

    @staticmethod
    def _buy_fill(price: Decimal) -> Decimal:
        return (price * (Decimal("1") + FORWARD_SLIPPAGE_BPS / BASIS_POINTS)).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _sell_fill(price: Decimal) -> Decimal:
        return (price * (Decimal("1") - FORWARD_SLIPPAGE_BPS / BASIS_POINTS)).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _pct(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
