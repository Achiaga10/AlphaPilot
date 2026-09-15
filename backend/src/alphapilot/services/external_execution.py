"""Observational manual-execution journal; never writes Forward economic state."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.external_execution import (
    ExternalActionStatus,
    ExternalExecutionCase,
    ExternalExecutionEvent,
    ExternalExecutionEventType,
    ExternalExecutionFill,
    ExternalReconciliationStatus,
)
from alphapilot.database.models.forward_portfolio import (
    ForwardOrder,
    ForwardOrderSide,
    ForwardOrderStatus,
    ForwardPosition,
    ForwardTrade,
)
from alphapilot.repositories.forward_portfolio import ForwardPortfolioRepository
from alphapilot.schemas.external_execution import (
    ExternalActionSchema,
    ExternalEventSchema,
    ExternalExecutionAnalyticsSchema,
    ExternalFillRequest,
    ExternalFillSchema,
    ExternalSkipReason,
    ExternalTradeComparisonSchema,
)

PCT = Decimal("100")
BPS = Decimal("10000")
PRICE_PRECISION = Decimal("0.00000001")
MONEY_PRECISION = Decimal("0.0001")
NEW_YORK = ZoneInfo("America/New_York")
MANUAL_SOURCE = "MANUAL_USER_RECORDED"


class ExternalExecutionNotFoundError(ValueError):
    pass


class ExternalExecutionConflictError(ValueError):
    pass


class ExternalExecutionService:
    def __init__(
        self, session: AsyncSession, *, now_provider: Callable[[], datetime] | None = None
    ) -> None:
        self.session = session
        self.forward_repo = ForwardPortfolioRepository(session)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_actions(self, portfolio_id: UUID) -> list[ExternalActionSchema]:
        await self._portfolio_exists(portfolio_id)
        result = await self.session.execute(
            select(ExternalExecutionCase, ForwardOrder)
            .join(ForwardOrder, ExternalExecutionCase.forward_order_id == ForwardOrder.id)
            .where(ExternalExecutionCase.portfolio_id == portfolio_id)
            .order_by(ForwardOrder.created_at.desc(), ForwardOrder.id)
        )
        pairs = result.all()
        if not pairs:
            return []
        case_ids = [case.id for case, _ in pairs]
        fill_result = await self.session.execute(
            select(ExternalExecutionFill)
            .where(ExternalExecutionFill.case_id.in_(case_ids))
            .order_by(ExternalExecutionFill.created_at, ExternalExecutionFill.id)
        )
        event_result = await self.session.execute(
            select(ExternalExecutionEvent)
            .where(ExternalExecutionEvent.case_id.in_(case_ids))
            .order_by(ExternalExecutionEvent.created_at, ExternalExecutionEvent.id)
        )
        fills: dict[UUID, list[ExternalExecutionFill]] = defaultdict(list)
        events: dict[UUID, list[ExternalExecutionEvent]] = defaultdict(list)
        for fill in fill_result.scalars():
            fills[fill.case_id].append(fill)
        for event in event_result.scalars():
            events[event.case_id].append(event)
        return [
            self._project(case, order, fills[case.id], events[case.id]) for case, order in pairs
        ]

    async def get_action(self, portfolio_id: UUID, case_id: UUID) -> ExternalActionSchema:
        case, order = await self._case_order(portfolio_id, case_id)
        fills = await self._fills(case.id)
        events = await self._events(case.id)
        return self._project(case, order, fills, events)

    async def record_fill(
        self, portfolio_id: UUID, case_id: UUID, request: ExternalFillRequest
    ) -> ExternalActionSchema:
        await self.forward_repo.advisory_lock(portfolio_id)
        case, order = await self._case_order(portfolio_id, case_id, for_update=True)
        expected_side = self._side(order)
        if request.side != expected_side:
            raise ValueError(f"Expected {expected_side} for this Forward action")
        if case.skipped_at is not None:
            raise ExternalExecutionConflictError("Skipped actions cannot accept a fill")
        if request.executed_at > self.now_provider() + timedelta(minutes=5):
            raise ValueError("Execution timestamp cannot be in the future")
        existing = await self.session.scalar(
            select(ExternalExecutionFill).where(
                ExternalExecutionFill.case_id == case.id,
                ExternalExecutionFill.request_key == request.request_key,
            )
        )
        if existing is not None:
            if (
                existing.side != request.side
                or existing.quantity != request.quantity
                or Decimal(existing.price) != request.price
                or existing.executed_at != request.executed_at
                or existing.fee != request.fee
                or existing.mark_complete != request.mark_complete
            ):
                raise ExternalExecutionConflictError(
                    "Idempotency key was already used for a different fill"
                )
            await self.session.rollback()
            return await self.get_action(portfolio_id, case_id)
        now = self.now_provider()
        fill = ExternalExecutionFill(
            case_id=case.id,
            request_key=request.request_key,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            executed_at=request.executed_at,
            fee=request.fee,
            mark_complete=request.mark_complete,
            source=MANUAL_SOURCE,
            created_at=now,
        )
        self.session.add(fill)
        await self.session.flush()
        case.recording_complete = case.recording_complete or request.mark_complete
        self._event(
            case,
            ExternalExecutionEventType.EXTERNAL_FILL_RECORDED,
            key=f"fill:{fill.id}:recorded",
            reason="USER_RECORDED_FILL",
            facts={
                "fill_id": str(fill.id),
                "quantity": fill.quantity,
                "price": str(fill.price),
                "fee": str(fill.fee) if fill.fee is not None else None,
                "mark_complete": fill.mark_complete,
            },
        )
        self._event(
            case,
            (
                ExternalExecutionEventType.EXTERNAL_ACTION_RECORDED
                if case.recording_complete
                else ExternalExecutionEventType.EXTERNAL_ACTION_PARTIAL
            ),
            key=f"fill:{fill.id}:status",
            reason="USER_RECORDED_FILL",
            facts={"fill_id": str(fill.id)},
        )
        self._event(
            case,
            ExternalExecutionEventType.EXTERNAL_RECONCILIATION_UPDATED,
            key=f"fill:{fill.id}:reconciled",
            reason="FILL_CHANGED",
            facts={"fill_id": str(fill.id)},
        )
        await self.session.commit()
        return await self.get_action(portfolio_id, case_id)

    async def skip(
        self, portfolio_id: UUID, case_id: UUID, reason: ExternalSkipReason
    ) -> ExternalActionSchema:
        await self.forward_repo.advisory_lock(portfolio_id)
        case, _ = await self._case_order(portfolio_id, case_id, for_update=True)
        if case.skipped_at is not None:
            if case.skip_reason != reason.value:
                raise ExternalExecutionConflictError("Action was skipped for a different reason")
            await self.session.rollback()
            return await self.get_action(portfolio_id, case_id)
        if any(fill.voided_at is None for fill in await self._fills(case.id)):
            raise ExternalExecutionConflictError(
                "Void recorded fills before marking action skipped"
            )
        case.skipped_at = self.now_provider()
        case.skip_reason = reason.value
        case.recording_complete = False
        self._event(
            case,
            ExternalExecutionEventType.EXTERNAL_ACTION_SKIPPED,
            key="action:skipped",
            reason=reason.value,
            facts={},
        )
        await self.session.commit()
        return await self.get_action(portfolio_id, case_id)

    async def void_fill(
        self, portfolio_id: UUID, fill_id: UUID, *, reason: str, request_key: str
    ) -> ExternalActionSchema:
        fill = await self.session.get(ExternalExecutionFill, fill_id)
        if fill is None:
            raise ExternalExecutionNotFoundError("External fill not found")
        case = await self.session.get(ExternalExecutionCase, fill.case_id)
        if case is None or case.portfolio_id != portfolio_id:
            raise ExternalExecutionNotFoundError("External fill not found")
        case_id = case.id
        await self.session.rollback()
        await self.forward_repo.advisory_lock(portfolio_id)
        case, _ = await self._case_order(portfolio_id, case_id, for_update=True)
        fill = await self.session.get(ExternalExecutionFill, fill_id, with_for_update=True)
        if fill is None or fill.case_id != case.id:
            raise ExternalExecutionNotFoundError("External fill not found")
        if fill.voided_at is not None:
            event = await self.session.scalar(
                select(ExternalExecutionEvent).where(
                    ExternalExecutionEvent.case_id == case.id,
                    ExternalExecutionEvent.idempotency_key == f"fill:{fill.id}:voided",
                )
            )
            if (
                event is None
                or event.facts.get("request_key") != request_key
                or fill.void_reason != reason
            ):
                raise ExternalExecutionConflictError("Fill was already voided")
            await self.session.rollback()
            return await self.get_action(portfolio_id, case_id)
        fill.voided_at = self.now_provider()
        fill.void_reason = reason
        fill.void_source = MANUAL_SOURCE
        active_fills = [item for item in await self._fills(case.id) if item.voided_at is None]
        case.recording_complete = any(item.mark_complete for item in active_fills)
        self._event(
            case,
            ExternalExecutionEventType.EXTERNAL_FILL_VOIDED,
            key=f"fill:{fill.id}:voided",
            reason="USER_CORRECTION",
            facts={"fill_id": str(fill.id), "request_key": request_key, "reason": reason},
        )
        self._event(
            case,
            ExternalExecutionEventType.EXTERNAL_RECONCILIATION_UPDATED,
            key=f"fill:{fill.id}:void_reconciled",
            reason="FILL_VOIDED",
            facts={"fill_id": str(fill.id)},
        )
        await self.session.commit()
        return await self.get_action(portfolio_id, case.id)

    async def trade_comparisons(self, portfolio_id: UUID) -> list[ExternalTradeComparisonSchema]:
        await self._portfolio_exists(portfolio_id)
        actions = await self.list_actions(portfolio_id)
        by_order = {action.forward_order_id: action for action in actions}
        trades = await self.forward_repo.trades(portfolio_id)
        positions_result = await self.session.execute(
            select(ForwardPosition).where(ForwardPosition.portfolio_id == portfolio_id)
        )
        positions = {position.id: position for position in positions_result.scalars()}
        exit_result = await self.session.execute(
            select(ForwardOrder).where(
                ForwardOrder.portfolio_id == portfolio_id,
                ForwardOrder.side == ForwardOrderSide.EXIT.value,
            )
        )
        exits = {order.position_id: order for order in exit_result.scalars()}
        comparisons: list[ExternalTradeComparisonSchema] = []
        for trade in trades:
            position = positions[trade.position_id]
            entry = by_order.get(position.entry_order_id)
            exit_order = exits.get(position.id)
            exit_action = by_order.get(exit_order.id) if exit_order else None
            comparisons.append(self._trade_comparison(trade, entry, exit_action))
        return comparisons

    async def analytics(self, portfolio_id: UUID) -> ExternalExecutionAnalyticsSchema:
        actions = await self.list_actions(portfolio_id)
        expected = [
            item for item in actions if item.status != ExternalActionStatus.VIRTUAL_CANCELLED
        ]
        recorded = [item for item in expected if item.status == ExternalActionStatus.RECORDED]
        skipped = [item for item in expected if item.status == ExternalActionStatus.SKIPPED]
        partial = [
            item for item in expected if item.status == ExternalActionStatus.PARTIALLY_RECORDED
        ]
        entry_bps = [
            item.price_difference_bps
            for item in recorded
            if item.side == "BUY" and item.price_difference_bps is not None
        ]
        exit_bps = [
            item.price_difference_bps
            for item in recorded
            if item.side == "SELL" and item.price_difference_bps is not None
        ]
        quantity_variances = [
            Decimal(item.share_variance_vs_virtual)
            for item in recorded
            if item.share_variance_vs_virtual is not None
        ]
        matched = [
            item
            for item in await self.trade_comparisons(portfolio_id)
            if item.completeness == "COMPLETE" and item.recorded_execution_pnl is not None
        ]
        virtual_pnl = sum((item.virtual_net_pnl for item in matched), Decimal("0"))
        recorded_pnl = sum(
            (
                item.recorded_execution_pnl
                for item in matched
                if item.recorded_execution_pnl is not None
            ),
            Decimal("0"),
        )
        return ExternalExecutionAnalyticsSchema(
            expected_actions=len(expected),
            recorded_actions=len(recorded),
            skipped_actions=len(skipped),
            missing_records=sum(
                item.status == ExternalActionStatus.AWAITING_RECORD for item in expected
            ),
            partial_actions=len(partial),
            actions_awaiting_execution=sum(
                item.status == ExternalActionStatus.AWAITING_ACTION for item in expected
            ),
            actions_awaiting_recording=sum(
                item.status == ExternalActionStatus.AWAITING_RECORD for item in expected
            ),
            diverged_actions=sum(
                item.reconciliation_status
                in {
                    ExternalReconciliationStatus.PRICE_DIVERGENCE,
                    ExternalReconciliationStatus.QUANTITY_DIVERGENCE,
                    ExternalReconciliationStatus.PRICE_AND_QUANTITY_DIVERGENCE,
                    ExternalReconciliationStatus.EXECUTED_AFTER_VIRTUAL_CANCEL,
                }
                for item in expected
            ),
            recording_rate_pct=self._rate(len(recorded), len(expected)),
            skip_rate_pct=self._rate(len(skipped), len(expected)),
            average_absolute_entry_difference_bps=self._average([abs(item) for item in entry_bps]),
            average_signed_entry_difference_bps=self._average(entry_bps),
            average_absolute_exit_difference_bps=self._average([abs(item) for item in exit_bps]),
            average_signed_exit_difference_bps=self._average(exit_bps),
            average_quantity_variance=self._average(quantity_variances),
            completed_fully_reconciled_trades=len(matched),
            matched_virtual_pnl=self._money(virtual_pnl) if matched else None,
            matched_recorded_execution_pnl=self._money(recorded_pnl) if matched else None,
            matched_pnl_difference=self._money(recorded_pnl - virtual_pnl) if matched else None,
        )

    async def _portfolio_exists(self, portfolio_id: UUID) -> None:
        if await self.forward_repo.get(portfolio_id) is None:
            raise ExternalExecutionNotFoundError("Forward Portfolio not found")

    async def _case_order(
        self, portfolio_id: UUID, case_id: UUID, *, for_update: bool = False
    ) -> tuple[ExternalExecutionCase, ForwardOrder]:
        statement = (
            select(ExternalExecutionCase, ForwardOrder)
            .join(ForwardOrder, ExternalExecutionCase.forward_order_id == ForwardOrder.id)
            .where(
                ExternalExecutionCase.id == case_id,
                ExternalExecutionCase.portfolio_id == portfolio_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ExternalExecutionCase)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            raise ExternalExecutionNotFoundError("External action not found")
        return row[0], row[1]

    async def _fills(self, case_id: UUID) -> list[ExternalExecutionFill]:
        result = await self.session.execute(
            select(ExternalExecutionFill)
            .where(ExternalExecutionFill.case_id == case_id)
            .order_by(ExternalExecutionFill.created_at, ExternalExecutionFill.id)
        )
        return list(result.scalars())

    async def _events(self, case_id: UUID) -> list[ExternalExecutionEvent]:
        result = await self.session.execute(
            select(ExternalExecutionEvent)
            .where(ExternalExecutionEvent.case_id == case_id)
            .order_by(ExternalExecutionEvent.created_at, ExternalExecutionEvent.id)
        )
        return list(result.scalars())

    def _project(
        self,
        case: ExternalExecutionCase,
        order: ForwardOrder,
        fills: list[ExternalExecutionFill],
        events: list[ExternalExecutionEvent],
    ) -> ExternalActionSchema:
        active = [item for item in fills if item.voided_at is None]
        shares = sum(item.quantity for item in active)
        notional = sum(
            (Decimal(item.quantity) * Decimal(item.price) for item in active), Decimal("0")
        )
        weighted = (
            (notional / Decimal(shares)).quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)
            if shares
            else None
        )
        fee_known = bool(active) and all(item.fee is not None for item in active)
        fees = (
            sum((Decimal(item.fee) for item in active if item.fee is not None), Decimal("0"))
            if fee_known
            else None
        )
        status = self._action_status(case, order, bool(active))
        virtual_shares = order.filled_shares
        virtual_price = (
            Decimal(order.modeled_fill_price) if order.modeled_fill_price is not None else None
        )
        virtual_notional = (
            self._money(Decimal(virtual_shares) * virtual_price)
            if virtual_shares is not None and virtual_price is not None
            else None
        )
        price_difference = (
            self._money(weighted - virtual_price)
            if weighted is not None and virtual_price is not None
            else None
        )
        price_bps = (
            self._precise((weighted - virtual_price) / virtual_price * BPS)
            if weighted is not None and virtual_price is not None and virtual_price > 0
            else None
        )
        first_at = min((item.executed_at for item in active), default=None)
        expected_date = order.planned_execution_session or order.actual_execution_session
        expected_open = (
            datetime.combine(expected_date, time(9, 30), tzinfo=NEW_YORK).astimezone(UTC)
            if expected_date is not None
            else None
        )
        timing_seconds = (
            round((first_at - expected_open).total_seconds())
            if first_at is not None and expected_open is not None
            else None
        )
        reconciliation = self._reconciliation(
            status, order, shares, weighted, virtual_shares, virtual_price
        )
        return ExternalActionSchema(
            id=case.id,
            forward_portfolio_id=case.portfolio_id,
            forward_order_id=order.id,
            position_id=order.position_id,
            ticker=order.ticker,
            side=self._side(order),
            strategy_id=order.strategy_id,
            strategy_version=order.strategy_version,
            broker=case.broker,
            provenance=case.provenance,
            source_signal_session=order.source_signal_session,
            planned_execution_session=order.planned_execution_session,
            actual_virtual_execution_session=order.actual_execution_session,
            expected_timing="Next eligible stored market session open",
            planned_shares=order.planned_shares,
            virtual_filled_shares=virtual_shares,
            virtual_order_status=ForwardOrderStatus(order.status),
            virtual_modeled_fill_price=virtual_price,
            loss_control_policy=order.loss_control_policy,
            loss_control_boundary=order.loss_control_boundary,
            decision_reason=order.reason_code,
            created_at=case.created_at,
            status=status,
            reconciliation_status=reconciliation,
            due_status=self._due_status(status, order),
            recorded_shares=shares,
            weighted_fill_price=weighted,
            recorded_notional=self._money(notional) if active else None,
            recorded_fees=self._money(fees) if fees is not None else None,
            fee_coverage_complete=fee_known,
            share_variance_vs_planned=shares - order.planned_shares if active else None,
            share_variance_vs_virtual=shares - virtual_shares
            if active and virtual_shares is not None
            else None,
            price_difference_per_share=price_difference,
            price_difference_bps=price_bps,
            virtual_notional=virtual_notional,
            notional_variance=self._money(notional - virtual_notional)
            if active and virtual_notional is not None
            else None,
            first_executed_at=first_at,
            timing_difference_seconds=timing_seconds,
            skip_reason=case.skip_reason,
            fills=[ExternalFillSchema.model_validate(item) for item in fills],
            events=[ExternalEventSchema.model_validate(item) for item in events],
        )

    def _action_status(
        self, case: ExternalExecutionCase, order: ForwardOrder, has_fills: bool
    ) -> ExternalActionStatus:
        if case.skipped_at is not None:
            return ExternalActionStatus.SKIPPED
        if has_fills:
            return (
                ExternalActionStatus.RECORDED
                if case.recording_complete
                else ExternalActionStatus.PARTIALLY_RECORDED
            )
        if order.status == ForwardOrderStatus.CANCELLED.value:
            return ExternalActionStatus.VIRTUAL_CANCELLED
        if order.status == ForwardOrderStatus.FILLED.value:
            return ExternalActionStatus.AWAITING_RECORD
        if (
            order.planned_execution_session is not None
            and self.now_provider().astimezone(NEW_YORK).date() >= order.planned_execution_session
        ):
            return ExternalActionStatus.AWAITING_RECORD
        return ExternalActionStatus.AWAITING_ACTION

    def _due_status(
        self, status: ExternalActionStatus, order: ForwardOrder
    ) -> Literal["UPCOMING", "AWAITING_RECORD", "OVERDUE_RECORDING", "DONE", "CANCELLED"]:
        if status == ExternalActionStatus.VIRTUAL_CANCELLED:
            return "CANCELLED"
        if status in {ExternalActionStatus.RECORDED, ExternalActionStatus.SKIPPED}:
            return "DONE"
        if status == ExternalActionStatus.PARTIALLY_RECORDED:
            return "AWAITING_RECORD"
        if status == ExternalActionStatus.AWAITING_ACTION:
            return "UPCOMING"
        due = order.planned_execution_session or order.actual_execution_session
        if due is not None and due < self.now_provider().astimezone(NEW_YORK).date():
            return "OVERDUE_RECORDING"
        return "AWAITING_RECORD"

    @staticmethod
    def _reconciliation(
        status: ExternalActionStatus,
        order: ForwardOrder,
        shares: int,
        weighted: Decimal | None,
        virtual_shares: int | None,
        virtual_price: Decimal | None,
    ) -> ExternalReconciliationStatus:
        if status == ExternalActionStatus.SKIPPED:
            return ExternalReconciliationStatus.SKIPPED
        if order.status == ForwardOrderStatus.CANCELLED.value:
            return (
                ExternalReconciliationStatus.EXECUTED_AFTER_VIRTUAL_CANCEL
                if shares
                else ExternalReconciliationStatus.VIRTUAL_CANCELLED
            )
        if status == ExternalActionStatus.PARTIALLY_RECORDED:
            return ExternalReconciliationStatus.PARTIAL
        if not shares:
            return (
                ExternalReconciliationStatus.INCOMPLETE
                if order.status == ForwardOrderStatus.PENDING.value
                else ExternalReconciliationStatus.MISSING_RECORD
            )
        if virtual_shares is None or virtual_price is None or weighted is None:
            return ExternalReconciliationStatus.INCOMPLETE
        quantity_differs = shares != virtual_shares
        price_differs = weighted != virtual_price
        if quantity_differs and price_differs:
            return ExternalReconciliationStatus.PRICE_AND_QUANTITY_DIVERGENCE
        if quantity_differs:
            return ExternalReconciliationStatus.QUANTITY_DIVERGENCE
        if price_differs:
            return ExternalReconciliationStatus.PRICE_DIVERGENCE
        return ExternalReconciliationStatus.ALIGNED

    def _trade_comparison(
        self,
        trade: ForwardTrade,
        entry: ExternalActionSchema | None,
        exit_action: ExternalActionSchema | None,
    ) -> ExternalTradeComparisonSchema:
        entry_shares = entry.recorded_shares if entry and entry.recorded_shares else None
        exit_shares = (
            exit_action.recorded_shares if exit_action and exit_action.recorded_shares else None
        )
        completeness: Literal[
            "COMPLETE",
            "MISSING_ENTRY",
            "MISSING_EXIT",
            "PARTIAL",
            "QUANTITY_MISMATCH",
            "FEES_UNKNOWN",
            "SKIPPED",
        ]
        if (entry and entry.status == ExternalActionStatus.SKIPPED) or (
            exit_action and exit_action.status == ExternalActionStatus.SKIPPED
        ):
            completeness = "SKIPPED"
        elif entry is None or entry_shares is None:
            completeness = "MISSING_ENTRY"
        elif exit_action is None or exit_shares is None:
            completeness = "MISSING_EXIT"
        elif (
            entry.status != ExternalActionStatus.RECORDED
            or exit_action.status != ExternalActionStatus.RECORDED
        ):
            completeness = "PARTIAL"
        elif entry_shares != exit_shares:
            completeness = "QUANTITY_MISMATCH"
        elif not entry.fee_coverage_complete or not exit_action.fee_coverage_complete:
            completeness = "FEES_UNKNOWN"
        else:
            completeness = "COMPLETE"
        gross = (
            self._money(exit_action.recorded_notional - entry.recorded_notional)
            if entry is not None
            and exit_action is not None
            and entry.recorded_notional is not None
            and exit_action.recorded_notional is not None
            and entry_shares == exit_shares
            and entry.status == ExternalActionStatus.RECORDED
            and exit_action.status == ExternalActionStatus.RECORDED
            else None
        )
        fees = (
            self._money(entry.recorded_fees + exit_action.recorded_fees)
            if entry is not None
            and exit_action is not None
            and entry.recorded_fees is not None
            and exit_action.recorded_fees is not None
            else None
        )
        net = self._money(gross - fees) if gross is not None and fees is not None else None
        return ExternalTradeComparisonSchema(
            forward_trade_id=trade.id,
            ticker=trade.ticker,
            entry_action_id=entry.id if entry else None,
            exit_action_id=exit_action.id if exit_action else None,
            completeness=completeness,
            virtual_shares=trade.shares,
            recorded_entry_shares=entry_shares,
            recorded_exit_shares=exit_shares,
            virtual_entry_price=trade.modeled_entry_price,
            recorded_entry_price=entry.weighted_fill_price if entry else None,
            virtual_exit_price=trade.modeled_exit_price,
            recorded_exit_price=exit_action.weighted_fill_price if exit_action else None,
            virtual_net_pnl=trade.net_pnl,
            recorded_gross_pnl=gross,
            recorded_execution_pnl=net,
            pnl_difference=self._money(net - trade.net_pnl) if net is not None else None,
            recorded_fees=fees,
            entry_price_difference=entry.price_difference_per_share if entry else None,
            exit_price_difference=exit_action.price_difference_per_share if exit_action else None,
            quantity_variance=entry_shares - trade.shares if entry_shares is not None else None,
        )

    def _event(
        self,
        case: ExternalExecutionCase,
        event_type: ExternalExecutionEventType,
        *,
        key: str,
        reason: str,
        facts: dict[str, object],
    ) -> None:
        self.session.add(
            ExternalExecutionEvent(
                portfolio_id=case.portfolio_id,
                case_id=case.id,
                event_type=event_type.value,
                idempotency_key=key,
                reason_code=reason,
                source=MANUAL_SOURCE,
                facts=facts,
                created_at=self.now_provider(),
            )
        )

    @staticmethod
    def _side(order: ForwardOrder) -> Literal["BUY", "SELL"]:
        return "BUY" if order.side == ForwardOrderSide.ENTRY.value else "SELL"

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)

    @staticmethod
    def _precise(value: Decimal) -> Decimal:
        return value.quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)

    @classmethod
    def _average(cls, values: list[Decimal]) -> Decimal | None:
        return cls._precise(sum(values, Decimal("0")) / Decimal(len(values))) if values else None

    @classmethod
    def _rate(cls, count: int, total: int) -> Decimal | None:
        return cls._precise(Decimal(count) / Decimal(total) * PCT) if total else None
