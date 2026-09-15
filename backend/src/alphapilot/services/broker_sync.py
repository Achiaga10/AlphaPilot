"""Observational Alpaca synchronization and conservative Forward matching."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from alphapilot.broker.alpaca_read_only import AlpacaReadOnlyClient
from alphapilot.core.config import Settings, settings
from alphapilot.database.models.broker_sync import (
    BrokerAccountSnapshot,
    BrokerExecution,
    BrokerExecutionMatchEvent,
    BrokerMatchState,
    BrokerOrderObservation,
    BrokerPositionSnapshot,
    BrokerSyncRun,
    BrokerSyncRunStatus,
)
from alphapilot.database.models.external_execution import (
    ExternalExecutionCase,
    ExternalExecutionFill,
)
from alphapilot.database.models.forward_portfolio import ForwardOrder, ForwardOrderSide
from alphapilot.schemas.broker_sync import (
    AlpacaSyncStatusSchema,
    BrokerAccountSchema,
    BrokerExecutionSchema,
    BrokerOrderSchema,
    BrokerPositionSchema,
)

PROVIDER = "ALPACA"
PROVENANCE = "ALPACA_READ_ONLY_SYNC"
USER_SOURCE = "MANUAL_USER_RECORDED"
NEW_YORK = ZoneInfo("America/New_York")


class ReadOnlyBrokerProvider(Protocol):
    async def get_account(self) -> dict[str, object]: ...

    async def get_positions(self) -> list[dict[str, object]]: ...

    async def get_orders(self, *, after: datetime) -> list[dict[str, object]]: ...

    async def get_fill_activities(self, *, after: datetime) -> list[dict[str, object]]: ...

    async def close(self) -> None: ...


class BrokerSyncNotConfiguredError(ValueError):
    pass


class BrokerSyncConflictError(ValueError):
    pass


ProviderFactory = Callable[[], ReadOnlyBrokerProvider]


class AlpacaBrokerSyncService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        config: Settings = settings,
        provider_factory: ProviderFactory | None = None,
        now_provider: Callable[[], datetime] | None = None,
        scheduler_running: bool = False,
    ) -> None:
        self.session = session
        self.config = config
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.provider_factory = provider_factory or self._default_provider
        self.scheduler_running = scheduler_running

    @property
    def configured(self) -> bool:
        return bool(self.config.ALPACA_API_KEY and self.config.ALPACA_SECRET_KEY)

    def _default_provider(self) -> AlpacaReadOnlyClient:
        return AlpacaReadOnlyClient(
            api_key=self.config.ALPACA_API_KEY,
            secret_key=self.config.ALPACA_SECRET_KEY,
            environment=self.config.ALPACA_ENVIRONMENT,
            timeout_seconds=self.config.ALPACA_SYNC_TIMEOUT_SECONDS,
        )

    async def sync_now(self) -> AlpacaSyncStatusSchema:
        if not self.config.ALPACA_SYNC_ENABLED:
            raise BrokerSyncNotConfiguredError("Alpaca read-only synchronization is disabled")
        if not self.configured:
            raise BrokerSyncNotConfiguredError(
                "Alpaca read-only synchronization credentials are not configured"
            )
        await self.session.execute(text("SELECT pg_advisory_xact_lock(2727, 1)"))
        now = self.now_provider()
        after = await self._requested_after(now)
        run = BrokerSyncRun(
            provider=PROVIDER,
            environment=self.config.ALPACA_ENVIRONMENT,
            status=BrokerSyncRunStatus.RUNNING.value,
            started_at=now,
            requested_after=after,
        )
        self.session.add(run)
        await self.session.flush()
        provider = self.provider_factory()
        try:
            account = await provider.get_account()
            positions = await provider.get_positions()
            orders = await provider.get_orders(after=after)
            activities = await provider.get_fill_activities(after=after)
            self._store_account(run, account, now)
            self._store_positions(run, positions, now)
            await self._store_orders(run, orders)
            new_executions = await self._store_executions(run, activities, now)
            await self.session.flush()
            await self._auto_match(new_executions, now)
            run.status = BrokerSyncRunStatus.SUCCEEDED.value
            run.completed_at = self.now_provider()
            run.high_watermark = max(
                (item.executed_at for item in new_executions), default=await self._watermark()
            )
            run.account_count = 1
            run.position_count = len(positions)
            run.order_count = len(orders)
            run.execution_count = len(activities)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed = BrokerSyncRun(
                provider=PROVIDER,
                environment=self.config.ALPACA_ENVIRONMENT,
                status=BrokerSyncRunStatus.FAILED.value,
                started_at=now,
                completed_at=self.now_provider(),
                requested_after=after,
                error_code=type(exc).__name__[:80],
                error_message="Alpaca read-only synchronization failed; review server logs.",
            )
            self.session.add(failed)
            await self.session.commit()
        finally:
            await provider.close()
        return await self.status()

    async def status(self) -> AlpacaSyncStatusSchema:
        environment = self.config.ALPACA_ENVIRONMENT
        latest = await self.session.scalar(
            select(BrokerSyncRun)
            .where(BrokerSyncRun.environment == environment)
            .order_by(BrokerSyncRun.started_at.desc())
            .limit(1)
        )
        success = await self.session.scalar(
            select(BrokerSyncRun)
            .where(
                BrokerSyncRun.environment == environment,
                BrokerSyncRun.status == BrokerSyncRunStatus.SUCCEEDED.value,
            )
            .order_by(BrokerSyncRun.completed_at.desc())
            .limit(1)
        )
        execution_count = await self._count(
            BrokerExecution, BrokerExecution.environment == environment
        )
        unmatched = await self._count(
            BrokerExecution,
            BrokerExecution.environment == environment,
            BrokerExecution.match_state.in_(
                [BrokerMatchState.UNMATCHED.value, BrokerMatchState.AMBIGUOUS.value]
            ),
        )
        completed = success.completed_at if success else None
        return AlpacaSyncStatusSchema(
            enabled=self.config.ALPACA_SYNC_ENABLED,
            configured=self.configured,
            environment=environment,
            scheduler_running=self.scheduler_running,
            status=(
                "DISABLED"
                if not self.config.ALPACA_SYNC_ENABLED
                else "MISCONFIGURED"
                if not self.configured
                else latest.status
                if latest is not None
                else "NEVER_RUN"
            ),
            last_attempt_at=latest.started_at if latest else None,
            last_success_at=completed,
            last_error=latest.error_message if latest else None,
            data_age_seconds=(
                max(0, round((self.now_provider() - completed).total_seconds()))
                if completed
                else None
            ),
            account_snapshots=await self._count(
                BrokerAccountSnapshot, BrokerAccountSnapshot.environment == environment
            ),
            positions=(success.position_count if success else 0),
            orders=await self._count(
                BrokerOrderObservation, BrokerOrderObservation.environment == environment
            ),
            executions=execution_count,
            unmatched_executions=unmatched,
            interval_seconds=self.config.ALPACA_SYNC_INTERVAL_SECONDS,
            initial_lookback_days=self.config.ALPACA_SYNC_INITIAL_LOOKBACK_DAYS,
            overlap_minutes=self.config.ALPACA_SYNC_OVERLAP_MINUTES,
        )

    async def account(self) -> BrokerAccountSchema | None:
        row = await self.session.scalar(
            select(BrokerAccountSnapshot)
            .where(BrokerAccountSnapshot.environment == self.config.ALPACA_ENVIRONMENT)
            .order_by(BrokerAccountSnapshot.observed_at.desc())
            .limit(1)
        )
        return BrokerAccountSchema.model_validate(row) if row else None

    async def positions(self) -> list[BrokerPositionSchema]:
        run = await self._latest_success()
        if run is None:
            return []
        rows = (
            await self.session.execute(
                select(BrokerPositionSnapshot)
                .where(BrokerPositionSnapshot.sync_run_id == run.id)
                .order_by(BrokerPositionSnapshot.symbol)
            )
        ).scalars()
        return [BrokerPositionSchema.model_validate(row) for row in rows]

    async def orders(self, *, limit: int = 200) -> list[BrokerOrderSchema]:
        rows = (
            await self.session.execute(
                select(BrokerOrderObservation)
                .where(BrokerOrderObservation.environment == self.config.ALPACA_ENVIRONMENT)
                .order_by(BrokerOrderObservation.broker_updated_at.desc().nullslast())
                .limit(limit)
            )
        ).scalars()
        return [BrokerOrderSchema.model_validate(row) for row in rows]

    async def executions(
        self, *, unmatched_only: bool = False, limit: int = 200
    ) -> list[BrokerExecutionSchema]:
        statement = select(BrokerExecution).where(
            BrokerExecution.environment == self.config.ALPACA_ENVIRONMENT
        )
        if unmatched_only:
            statement = statement.where(
                BrokerExecution.match_state.in_(
                    [BrokerMatchState.UNMATCHED.value, BrokerMatchState.AMBIGUOUS.value]
                )
            )
        rows = (
            await self.session.execute(
                statement.order_by(BrokerExecution.executed_at.desc()).limit(limit)
            )
        ).scalars()
        return [BrokerExecutionSchema.model_validate(row) for row in rows]

    async def manual_match(
        self,
        execution_id: UUID,
        case_id: UUID,
        *,
        reason: str,
        request_key: str,
    ) -> BrokerExecutionSchema:
        await self.session.execute(text("SELECT pg_advisory_xact_lock(2727, 1)"))
        execution = await self._execution(execution_id, for_update=True)
        case, order = await self._case_order(case_id)
        if execution.symbol != order.ticker or execution.side != self._order_side(order):
            raise ValueError("Broker execution ticker and side must match the Forward action")
        await self._transition(
            execution,
            BrokerMatchState.MANUAL_MATCHED,
            case=case,
            reason=reason,
            request_key=request_key,
        )
        await self.session.flush()
        linked = list(
            (
                await self.session.execute(
                    select(BrokerExecution).where(BrokerExecution.external_case_id == case.id)
                )
            ).scalars()
        )
        if await self._canonical_match_state(case.id, linked) == BrokerMatchState.CONFLICT:
            for item in linked:
                item.match_state = BrokerMatchState.CONFLICT.value
                item.match_reason = "MANUAL_AND_BROKER_FACTS_DIFFER"
        await self.session.commit()
        return BrokerExecutionSchema.model_validate(execution)

    async def unlink(
        self, execution_id: UUID, *, reason: str, request_key: str
    ) -> BrokerExecutionSchema:
        await self.session.execute(text("SELECT pg_advisory_xact_lock(2727, 1)"))
        execution = await self._execution(execution_id, for_update=True)
        await self._transition(
            execution,
            BrokerMatchState.UNMATCHED,
            case=None,
            reason=reason,
            request_key=request_key,
        )
        execution.match_reason = "MANUALLY_UNLINKED"
        await self.session.commit()
        return BrokerExecutionSchema.model_validate(execution)

    async def ignore(
        self, execution_id: UUID, *, reason: str, request_key: str
    ) -> BrokerExecutionSchema:
        await self.session.execute(text("SELECT pg_advisory_xact_lock(2727, 1)"))
        execution = await self._execution(execution_id, for_update=True)
        await self._transition(
            execution,
            BrokerMatchState.IGNORED_EXTERNAL,
            case=None,
            reason=reason,
            request_key=request_key,
        )
        execution.ignored_reason = reason
        await self.session.commit()
        return BrokerExecutionSchema.model_validate(execution)

    async def _requested_after(self, now: datetime) -> datetime:
        watermark = await self._watermark()
        if watermark is None:
            return now - timedelta(days=self.config.ALPACA_SYNC_INITIAL_LOOKBACK_DAYS)
        return watermark - timedelta(minutes=self.config.ALPACA_SYNC_OVERLAP_MINUTES)

    async def _watermark(self) -> datetime | None:
        return cast(
            datetime | None,
            await self.session.scalar(
                select(func.max(BrokerExecution.executed_at)).where(
                    BrokerExecution.environment == self.config.ALPACA_ENVIRONMENT
                )
            ),
        )

    def _store_account(
        self, run: BrokerSyncRun, payload: dict[str, object], observed_at: datetime
    ) -> None:
        self.session.add(
            BrokerAccountSnapshot(
                sync_run_id=run.id,
                provider=PROVIDER,
                environment=run.environment,
                broker_account_id=self._required(payload, "id"),
                status=self._required(payload, "status"),
                currency=str(payload.get("currency") or "USD"),
                cash=self._decimal(payload, "cash"),
                equity=self._decimal(payload, "equity"),
                buying_power=self._decimal(payload, "buying_power"),
                observed_at=observed_at,
            )
        )

    def _store_positions(
        self, run: BrokerSyncRun, payloads: list[dict[str, object]], observed_at: datetime
    ) -> None:
        for payload in payloads:
            quantity = abs(self._decimal(payload, "qty"))
            self.session.add(
                BrokerPositionSnapshot(
                    sync_run_id=run.id,
                    provider=PROVIDER,
                    environment=run.environment,
                    symbol=self._required(payload, "symbol").upper(),
                    side=str(payload.get("side") or "long").upper(),
                    quantity=quantity,
                    average_entry_price=self._optional_decimal(payload.get("avg_entry_price")),
                    current_price=self._optional_decimal(payload.get("current_price")),
                    market_value=self._optional_decimal(payload.get("market_value")),
                    unrealized_pnl=self._optional_decimal(payload.get("unrealized_pl")),
                    observed_at=observed_at,
                )
            )

    async def _store_orders(self, run: BrokerSyncRun, payloads: list[dict[str, object]]) -> None:
        for payload in payloads:
            native_id = self._required(payload, "id")
            row = await self.session.scalar(
                select(BrokerOrderObservation).where(
                    BrokerOrderObservation.environment == run.environment,
                    BrokerOrderObservation.broker_order_id == native_id,
                )
            )
            values: dict[str, object] = {
                "last_sync_run_id": run.id,
                "provider": PROVIDER,
                "environment": run.environment,
                "broker_order_id": native_id,
                "client_order_id": self._optional_string(payload.get("client_order_id")),
                "symbol": self._required(payload, "symbol").upper(),
                "side": self._required(payload, "side").upper(),
                "status": self._required(payload, "status").upper(),
                "order_type": str(payload.get("type") or "UNKNOWN").upper(),
                "quantity": self._optional_decimal(payload.get("qty")),
                "filled_quantity": self._optional_decimal(payload.get("filled_qty"))
                or Decimal("0"),
                "filled_average_price": self._optional_decimal(payload.get("filled_avg_price")),
                "submitted_at": self._optional_datetime(payload.get("submitted_at")),
                "broker_updated_at": self._optional_datetime(payload.get("updated_at")),
            }
            if row is None:
                self.session.add(BrokerOrderObservation(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

    async def _store_executions(
        self,
        run: BrokerSyncRun,
        payloads: list[dict[str, object]],
        observed_at: datetime,
    ) -> list[BrokerExecution]:
        created: list[BrokerExecution] = []
        for payload in payloads:
            activity_id = self._required(payload, "id")
            existing = await self.session.scalar(
                select(BrokerExecution).where(
                    BrokerExecution.environment == run.environment,
                    BrokerExecution.broker_activity_id == activity_id,
                )
            )
            if existing is not None:
                continue
            side = self._required(payload, "side").upper()
            if side not in {"BUY", "SELL"}:
                raise ValueError("Alpaca fill activity contains an unsupported side")
            execution = BrokerExecution(
                first_sync_run_id=run.id,
                provider=PROVIDER,
                provenance=PROVENANCE,
                environment=run.environment,
                broker_activity_id=activity_id,
                broker_order_id=self._optional_string(payload.get("order_id")),
                symbol=self._required(payload, "symbol").upper(),
                side=side,
                quantity=self._decimal(payload, "qty"),
                price=self._decimal(payload, "price"),
                fee=self._optional_decimal(payload.get("fee")),
                executed_at=self._datetime(payload, "transaction_time"),
                match_state=BrokerMatchState.UNMATCHED.value,
                match_reason="NOT_EVALUATED",
                created_at=observed_at,
            )
            self.session.add(execution)
            created.append(execution)
        return created

    async def _auto_match(self, executions: list[BrokerExecution], now: datetime) -> None:
        grouped: dict[str, list[BrokerExecution]] = {}
        for execution in executions:
            key = execution.broker_order_id or execution.broker_activity_id
            grouped.setdefault(key, []).append(execution)
        by_window: dict[tuple[str, str, date], list[tuple[str, list[BrokerExecution]]]] = {}
        for group_key, group in grouped.items():
            first = min(group, key=lambda item: item.executed_at)
            execution_date = first.executed_at.astimezone(NEW_YORK).date()
            by_window.setdefault((first.symbol, first.side, execution_date), []).append(
                (group_key, group)
            )
        for order_groups in by_window.values():
            if len(order_groups) > 1:
                for _, group in order_groups:
                    for execution in group:
                        execution.match_state = BrokerMatchState.AMBIGUOUS.value
                        execution.match_reason = "MULTIPLE_BROKER_ORDER_GROUPS"
                continue
            group_key, group = order_groups[0]
            first = min(group, key=lambda item: item.executed_at)
            execution_date = first.executed_at.astimezone(NEW_YORK).date()
            candidates = (
                await self.session.execute(
                    select(ExternalExecutionCase, ForwardOrder)
                    .join(ForwardOrder, ExternalExecutionCase.forward_order_id == ForwardOrder.id)
                    .where(
                        ForwardOrder.ticker == first.symbol,
                        ForwardOrder.side
                        == (
                            ForwardOrderSide.ENTRY.value
                            if first.side == "BUY"
                            else ForwardOrderSide.EXIT.value
                        ),
                        func.coalesce(
                            ForwardOrder.actual_execution_session,
                            ForwardOrder.planned_execution_session,
                        )
                        == execution_date,
                    )
                )
            ).all()
            if len(candidates) == 1:
                case, _ = candidates[0]
                prior_links = (
                    await self.session.execute(
                        select(
                            BrokerExecution.broker_order_id,
                            BrokerExecution.broker_activity_id,
                        ).where(BrokerExecution.external_case_id == case.id)
                    )
                ).all()
                prior_group_keys = {
                    broker_order_id or broker_activity_id
                    for broker_order_id, broker_activity_id in prior_links
                }
                if prior_group_keys and group_key not in prior_group_keys:
                    for execution in group:
                        execution.match_state = BrokerMatchState.AMBIGUOUS.value
                        execution.match_reason = "DISTINCT_BROKER_ORDER_ALREADY_LINKED"
                    continue
                state = await self._canonical_match_state(case.id, group)
                for execution in group:
                    execution.external_case_id = case.id
                    execution.match_state = state.value
                    execution.match_reason = (
                        "MANUAL_AND_BROKER_FACTS_DIFFER"
                        if state == BrokerMatchState.CONFLICT
                        else "EXACT_SYMBOL_SIDE_SESSION_SINGLE_CASE"
                    )
                    execution.matched_at = now
            elif len(candidates) > 1:
                for execution in group:
                    execution.match_state = BrokerMatchState.AMBIGUOUS.value
                    execution.match_reason = "MULTIPLE_FORWARD_CASES"
            else:
                for execution in group:
                    execution.match_state = BrokerMatchState.UNMATCHED.value
                    execution.match_reason = "OUTSIDE_FORWARD_OR_EXECUTION_WINDOW"

    async def _canonical_match_state(
        self, case_id: UUID, broker_group: list[BrokerExecution]
    ) -> BrokerMatchState:
        manual = list(
            (
                await self.session.execute(
                    select(ExternalExecutionFill).where(
                        ExternalExecutionFill.case_id == case_id,
                        ExternalExecutionFill.voided_at.is_(None),
                    )
                )
            ).scalars()
        )
        if not manual:
            return BrokerMatchState.AUTO_MATCHED
        manual_quantity = sum((Decimal(item.quantity) for item in manual), Decimal("0"))
        broker_quantity = sum((item.quantity for item in broker_group), Decimal("0"))
        manual_notional = sum(
            (Decimal(item.quantity) * Decimal(item.price) for item in manual), Decimal("0")
        )
        broker_notional = sum((item.quantity * item.price for item in broker_group), Decimal("0"))
        if manual_quantity == broker_quantity and manual_notional == broker_notional:
            return BrokerMatchState.AUTO_MATCHED
        return BrokerMatchState.CONFLICT

    async def _transition(
        self,
        execution: BrokerExecution,
        state: BrokerMatchState,
        *,
        case: ExternalExecutionCase | None,
        reason: str,
        request_key: str,
    ) -> None:
        existing = await self.session.scalar(
            select(BrokerExecutionMatchEvent).where(
                BrokerExecutionMatchEvent.execution_id == execution.id,
                BrokerExecutionMatchEvent.request_key == request_key,
            )
        )
        if existing is not None:
            if existing.to_state != state.value or existing.new_case_id != (
                case.id if case else None
            ):
                raise BrokerSyncConflictError("Match request key was reused for another change")
            return
        previous_state = execution.match_state
        previous_case = execution.external_case_id
        now = self.now_provider()
        execution.match_state = state.value
        execution.match_reason = reason
        execution.external_case_id = case.id if case else None
        execution.matched_at = now if case else None
        if state != BrokerMatchState.IGNORED_EXTERNAL:
            execution.ignored_reason = None
        self.session.add(
            BrokerExecutionMatchEvent(
                execution_id=execution.id,
                from_state=previous_state,
                to_state=state.value,
                previous_case_id=previous_case,
                new_case_id=case.id if case else None,
                request_key=request_key,
                reason=reason,
                source=USER_SOURCE,
                facts={},
                created_at=now,
            )
        )

    async def _execution(self, execution_id: UUID, *, for_update: bool) -> BrokerExecution:
        statement = select(BrokerExecution).where(
            BrokerExecution.id == execution_id,
            BrokerExecution.environment == self.config.ALPACA_ENVIRONMENT,
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        if row is None:
            raise ValueError("Broker execution not found")
        return row

    async def _case_order(self, case_id: UUID) -> tuple[ExternalExecutionCase, ForwardOrder]:
        row = (
            await self.session.execute(
                select(ExternalExecutionCase, ForwardOrder)
                .join(ForwardOrder, ExternalExecutionCase.forward_order_id == ForwardOrder.id)
                .where(ExternalExecutionCase.id == case_id)
            )
        ).one_or_none()
        if row is None:
            raise ValueError("Forward external action not found")
        return row[0], row[1]

    async def _latest_success(self) -> BrokerSyncRun | None:
        return cast(
            BrokerSyncRun | None,
            await self.session.scalar(
                select(BrokerSyncRun)
                .where(
                    BrokerSyncRun.environment == self.config.ALPACA_ENVIRONMENT,
                    BrokerSyncRun.status == BrokerSyncRunStatus.SUCCEEDED.value,
                )
                .order_by(BrokerSyncRun.completed_at.desc())
                .limit(1)
            ),
        )

    async def _count(self, model: type[object], *criteria: ColumnElement[bool]) -> int:
        value = await self.session.scalar(select(func.count()).select_from(model).where(*criteria))
        return int(value or 0)

    @staticmethod
    def _order_side(order: ForwardOrder) -> str:
        return "BUY" if order.side == ForwardOrderSide.ENTRY.value else "SELL"

    @staticmethod
    def _required(payload: dict[str, object], field: str) -> str:
        value = payload.get(field)
        if value is None or not str(value).strip():
            raise ValueError(f"Alpaca response is missing required field {field}")
        return str(value).strip()

    @classmethod
    def _decimal(cls, payload: dict[str, object], field: str) -> Decimal:
        value = cls._optional_decimal(payload.get(field))
        if value is None:
            raise ValueError(f"Alpaca response is missing required decimal field {field}")
        if not value.is_finite():
            raise ValueError(f"Alpaca response contains invalid decimal field {field}")
        return value

    @staticmethod
    def _optional_decimal(value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Alpaca response contains an invalid decimal") from exc
        if not result.is_finite():
            raise ValueError("Alpaca response contains a non-finite decimal")
        return result

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value).strip() if value is not None and str(value).strip() else None

    @classmethod
    def _datetime(cls, payload: dict[str, object], field: str) -> datetime:
        result = cls._optional_datetime(payload.get(field))
        if result is None:
            raise ValueError(f"Alpaca response is missing required timestamp field {field}")
        return result

    @staticmethod
    def _optional_datetime(value: object) -> datetime | None:
        if value is None or value == "":
            return None
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("Alpaca timestamps must include a timezone")
        return result.astimezone(UTC)
