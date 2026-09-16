"""Deterministic, observational production-health evaluation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.core.config import Settings, settings
from alphapilot.database.models.broker_sync import (
    BrokerExecution,
    BrokerMatchState,
    BrokerPositionSnapshot,
    BrokerSyncRun,
    BrokerSyncRunStatus,
)
from alphapilot.database.models.forward_portfolio import (
    ForwardCycleStatus,
    ForwardPosition,
    ForwardPositionStatus,
)
from alphapilot.database.models.operations import (
    OperationalEventType,
    OperationalHealth,
    OperationalIncident,
    OperationalIncidentEvent,
    OperationalIncidentStatus,
    OperationalIncidentType,
    OperationalSeverity,
    OperationalSourceDomain,
)
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.forward_portfolio import ForwardPortfolioRepository
from alphapilot.schemas.external_execution import ExternalActionSchema
from alphapilot.schemas.operations import (
    BrokerOperationsSchema,
    DailyOperationsSummarySchema,
    ForwardOperationsSchema,
    OperationalIncidentEventSchema,
    OperationalIncidentSchema,
    OperationsEvaluationSchema,
    OperationsHealthSchema,
    PositionDriftSchema,
    StartupCheckSchema,
)
from alphapilot.services.broker_sync import AlpacaBrokerSyncService
from alphapilot.services.external_execution import ExternalExecutionService

EXPECTED_SCHEMA_REVISION = "c28a0f1b2d3e"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IncidentCondition:
    incident_type: OperationalIncidentType
    severity: OperationalSeverity
    source_domain: OperationalSourceDomain
    source_identity: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.incident_type.value}:{self.source_domain.value}:{self.source_identity}"


@dataclass(slots=True)
class OperationsSnapshot:
    evaluated_at: datetime
    conditions: list[IncidentCondition]
    forward: ForwardOperationsSchema
    broker: BrokerOperationsSchema
    drifts: list[PositionDriftSchema]
    startup: StartupCheckSchema
    expected_manual_buys: int = 0
    expected_manual_sells: int = 0
    overdue_actions: int = 0
    unmatched: int = 0
    ambiguous: int = 0
    conflicts: int = 0


class OperationsIncidentNotFoundError(ValueError):
    pass


class OperationsIncidentConflictError(ValueError):
    pass


class OperationsMonitor:
    """Reads operational evidence and writes only the Operations incident domain."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        config: Settings = settings,
        now_provider: Callable[[], datetime] | None = None,
        scheduler_context: Callable[[], dict[str, Any]] | None = None,
        monitor_running: bool = False,
    ) -> None:
        self.session = session
        self.config = config
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.scheduler_context = scheduler_context or (lambda: {})
        self.monitor_running = monitor_running
        self.forward_repo = ForwardPortfolioRepository(session)

    async def evaluate(self) -> OperationsEvaluationSchema:
        await self.session.execute(text("SELECT pg_advisory_xact_lock(2828, 1)"))
        snapshot = await self._snapshot()
        active_rows = list(
            (
                await self.session.execute(
                    select(OperationalIncident).where(
                        OperationalIncident.status.in_(
                            [
                                OperationalIncidentStatus.OPEN.value,
                                OperationalIncidentStatus.ACKNOWLEDGED.value,
                            ]
                        )
                    )
                )
            ).scalars()
        )
        active = {row.deduplication_key: row for row in active_rows}
        observed = {condition.key: condition for condition in snapshot.conditions}
        opened = updated = resolved = 0

        for key, condition in observed.items():
            row = active.get(key)
            if row is None:
                occurrence = (
                    await self.session.scalar(
                        select(func.max(OperationalIncident.occurrence)).where(
                            OperationalIncident.deduplication_key == key
                        )
                    )
                    or 0
                ) + 1
                row = OperationalIncident(
                    incident_type=condition.incident_type.value,
                    severity=condition.severity.value,
                    status=OperationalIncidentStatus.OPEN.value,
                    source_domain=condition.source_domain.value,
                    source_identity=condition.source_identity,
                    deduplication_key=key,
                    active_deduplication_key=key,
                    occurrence=occurrence,
                    opened_at=snapshot.evaluated_at,
                    last_observed_at=snapshot.evaluated_at,
                    summary=condition.summary,
                    evidence=condition.evidence,
                )
                self.session.add(row)
                await self.session.flush()
                self._event(
                    row,
                    OperationalEventType.OPENED,
                    None,
                    OperationalIncidentStatus.OPEN,
                    "Condition first observed",
                    condition.evidence,
                    snapshot.evaluated_at,
                )
                opened += 1
                logger.warning(
                    "operational_incident_opened type=%s severity=%s source=%s",
                    condition.incident_type.value,
                    condition.severity.value,
                    condition.source_identity,
                )
                continue
            changed = (
                row.severity != condition.severity.value
                or row.summary != condition.summary
                or row.evidence != condition.evidence
            )
            previous_status = OperationalIncidentStatus(row.status)
            row.last_observed_at = snapshot.evaluated_at
            row.severity = condition.severity.value
            row.summary = condition.summary
            row.evidence = condition.evidence
            if changed:
                self._event(
                    row,
                    OperationalEventType.UPDATED,
                    previous_status,
                    previous_status,
                    "Material condition facts changed",
                    condition.evidence,
                    snapshot.evaluated_at,
                )
                updated += 1

        for key, row in active.items():
            if key in observed:
                continue
            previous_status = OperationalIncidentStatus(row.status)
            row.status = OperationalIncidentStatus.RESOLVED.value
            row.resolved_at = snapshot.evaluated_at
            row.active_deduplication_key = None
            self._event(
                row,
                OperationalEventType.RESOLVED,
                previous_status,
                OperationalIncidentStatus.RESOLVED,
                "Condition no longer observed",
                row.evidence,
                snapshot.evaluated_at,
            )
            resolved += 1
            logger.info(
                "operational_incident_resolved type=%s source=%s",
                row.incident_type,
                row.source_identity,
            )

        await self.session.commit()
        overall = self._overall(snapshot.conditions)
        return OperationsEvaluationSchema(
            evaluated_at=snapshot.evaluated_at,
            opened=opened,
            updated=updated,
            resolved=resolved,
            overall_health=overall,
        )

    async def health(self) -> OperationsHealthSchema:
        snapshot = await self._snapshot()
        incidents = await self.list_incidents(active_only=True)
        critical = sum(item.severity == OperationalSeverity.CRITICAL for item in incidents)
        warning = sum(item.severity == OperationalSeverity.WARNING for item in incidents)
        info = sum(item.severity == OperationalSeverity.INFO for item in incidents)
        context = self.scheduler_context()
        return OperationsHealthSchema(
            overall_health=self._health_from_counts(critical, warning),
            critical_count=critical,
            warning_count=warning,
            info_count=info,
            evaluated_at=snapshot.evaluated_at,
            monitor_running=self.monitor_running,
            monitor_status=str(context.get("operations_status", "READY")),
            active_incidents=incidents,
            forward=snapshot.forward,
            broker=snapshot.broker,
            position_drifts=snapshot.drifts,
            startup=snapshot.startup,
        )

    async def daily_summary(self) -> DailyOperationsSummarySchema:
        health = await self.health()
        snapshot = await self._snapshot()
        return DailyOperationsSummarySchema(
            generated_at=snapshot.evaluated_at,
            overall_health=health.overall_health,
            critical_count=health.critical_count,
            warning_count=health.warning_count,
            forward=snapshot.forward,
            expected_manual_buys=snapshot.expected_manual_buys,
            expected_manual_sells=snapshot.expected_manual_sells,
            overdue_actions=snapshot.overdue_actions,
            broker=snapshot.broker,
            unmatched_broker_activity=snapshot.unmatched,
            ambiguous_matches=snapshot.ambiguous,
            execution_conflicts=snapshot.conflicts,
            position_drift_count=len(snapshot.drifts),
            latest_completed_market_session=snapshot.forward.latest_completed_market_session,
            latest_forward_processed_session=snapshot.forward.latest_processed_session,
        )

    async def list_incidents(
        self,
        *,
        status: OperationalIncidentStatus | None = None,
        severity: OperationalSeverity | None = None,
        incident_type: OperationalIncidentType | None = None,
        source_domain: OperationalSourceDomain | None = None,
        active_only: bool = False,
    ) -> list[OperationalIncidentSchema]:
        statement = select(OperationalIncident)
        if active_only:
            statement = statement.where(
                OperationalIncident.status.in_(
                    [
                        OperationalIncidentStatus.OPEN.value,
                        OperationalIncidentStatus.ACKNOWLEDGED.value,
                    ]
                )
            )
        if status is not None:
            statement = statement.where(OperationalIncident.status == status.value)
        if severity is not None:
            statement = statement.where(OperationalIncident.severity == severity.value)
        if incident_type is not None:
            statement = statement.where(OperationalIncident.incident_type == incident_type.value)
        if source_domain is not None:
            statement = statement.where(OperationalIncident.source_domain == source_domain.value)
        severity_order = func.array_position(
            [
                OperationalSeverity.CRITICAL.value,
                OperationalSeverity.WARNING.value,
                OperationalSeverity.INFO.value,
            ],
            OperationalIncident.severity,
        )
        rows = list(
            (
                await self.session.execute(
                    statement.order_by(severity_order, OperationalIncident.opened_at.desc())
                )
            ).scalars()
        )
        return [await self._schema(row, include_events=False) for row in rows]

    async def incident(self, incident_id: UUID) -> OperationalIncidentSchema:
        row = await self.session.get(OperationalIncident, incident_id)
        if row is None:
            raise OperationsIncidentNotFoundError("Operational incident not found")
        return await self._schema(row, include_events=True)

    async def acknowledge(self, incident_id: UUID, reason: str) -> OperationalIncidentSchema:
        await self.session.execute(text("SELECT pg_advisory_xact_lock(2828, 1)"))
        row = await self.session.get(OperationalIncident, incident_id, with_for_update=True)
        if row is None:
            raise OperationsIncidentNotFoundError("Operational incident not found")
        if row.status == OperationalIncidentStatus.RESOLVED.value:
            raise OperationsIncidentConflictError("Resolved incidents cannot be acknowledged")
        if row.status == OperationalIncidentStatus.OPEN.value:
            now = self.now_provider()
            row.status = OperationalIncidentStatus.ACKNOWLEDGED.value
            row.acknowledged_at = now
            self._event(
                row,
                OperationalEventType.ACKNOWLEDGED,
                OperationalIncidentStatus.OPEN,
                OperationalIncidentStatus.ACKNOWLEDGED,
                reason,
                {},
                now,
                source="USER",
            )
            await self.session.commit()
            logger.info("operational_incident_acknowledged id=%s", row.id)
        return await self._schema(row, include_events=True)

    async def _snapshot(self) -> OperationsSnapshot:
        now = self.now_provider()
        context = self.scheduler_context()
        conditions: list[IncidentCondition] = []
        portfolio = await self.forward_repo.get_current()
        completed_through = CompletedDailySessionPolicy(
            now_provider=self.now_provider
        ).completed_through()
        latest_market = await self.forward_repo.latest_completed_session(completed_through)
        pending_sessions: list[date] = []
        latest_cycle = None
        positions: list[ForwardPosition] = []
        actions: list[ExternalActionSchema] = []
        if portfolio is not None:
            if latest_market is not None and latest_market >= portfolio.forward_start_session:
                pending_sessions = await self.forward_repo.completed_sessions(
                    start=portfolio.forward_start_session,
                    end=latest_market,
                    after=portfolio.last_processed_session,
                )
            latest_cycle = await self.forward_repo.latest_cycle(portfolio.id)
            positions = await self.forward_repo.positions(portfolio.id)
            actions = await ExternalExecutionService(
                self.session, now_provider=self.now_provider
            ).list_actions(portfolio.id)

        forward_status = str(context.get("forward_status", "NEVER_RUN"))
        forward_running = bool(context.get("forward_running", False))
        forward = ForwardOperationsSchema(
            status=portfolio.status if portfolio else "NOT_INITIALIZED",
            scheduler_status=forward_status,
            scheduler_running=forward_running,
            cash=portfolio.cash_balance if portfolio else None,
            equity=portfolio.equity if portfolio else None,
            open_positions=sum(
                item.status == ForwardPositionStatus.OPEN.value for item in positions
            ),
            pending_sessions=len(pending_sessions),
            latest_processed_session=portfolio.last_processed_session if portfolio else None,
            latest_completed_market_session=latest_market,
        )
        if portfolio is not None:
            pid = str(portfolio.id)
            if portfolio.status == "PAUSED":
                conditions.append(
                    self._condition(
                        "FORWARD_PORTFOLIO_PAUSED",
                        "INFO",
                        "FORWARD",
                        pid,
                        "Forward portfolio is intentionally paused",
                        {"status": portfolio.status},
                    )
                )
            if forward_status == "FAILED" or portfolio.last_error:
                conditions.append(
                    self._condition(
                        "FORWARD_ENGINE_FAILED",
                        "WARNING",
                        "FORWARD",
                        pid,
                        "Forward processing most recently failed",
                        {"scheduler_status": forward_status, "last_error": portfolio.last_error},
                    )
                )
            if latest_cycle is not None and latest_cycle.status == ForwardCycleStatus.FAILED.value:
                conditions.append(
                    self._condition(
                        "FORWARD_CYCLE_FAILED",
                        "WARNING",
                        "FORWARD",
                        str(latest_cycle.id),
                        f"Forward cycle failed for {latest_cycle.trading_session}",
                        {
                            "session": str(latest_cycle.trading_session),
                            "error_code": latest_cycle.error_code,
                        },
                    )
                )
            if pending_sessions:
                conditions.append(
                    self._condition(
                        "FORWARD_PENDING_SESSIONS",
                        "WARNING",
                        "FORWARD",
                        pid,
                        f"{len(pending_sessions)} completed session(s) await Forward processing",
                        {"pending_sessions": [str(item) for item in pending_sessions]},
                    )
                )
                stale_seconds = self.config.FORWARD_PORTFOLIO_SCHEDULER_INTERVAL_SECONDS * 2
                if (
                    portfolio.last_successful_cycle is None
                    or (now - portfolio.last_successful_cycle).total_seconds() > stale_seconds
                ):
                    conditions.append(
                        self._condition(
                            "FORWARD_ENGINE_STALE",
                            "WARNING",
                            "FORWARD",
                            pid,
                            "Forward processing is stale while completed sessions are pending",
                            {
                                "last_successful_cycle": portfolio.last_successful_cycle.isoformat()
                                if portfolio.last_successful_cycle
                                else None,
                                "threshold_seconds": stale_seconds,
                            },
                        )
                    )
            if latest_market is None:
                conditions.append(
                    self._condition(
                        "MARKET_DATA_MISSING",
                        "WARNING",
                        "MARKET_DATA",
                        "SPY",
                        "No completed SPY market session is stored",
                        {"completed_through": str(completed_through)},
                    )
                )
            market_last_completed = context.get("market_last_completed")
            authoritative_market_session = (
                date.fromisoformat(market_last_completed)
                if isinstance(market_last_completed, str)
                else None
            )
            if (
                latest_market is not None
                and authoritative_market_session is not None
                and latest_market < authoritative_market_session
            ):
                conditions.append(
                    self._condition(
                        "MARKET_DATA_STALE",
                        "WARNING",
                        "MARKET_DATA",
                        "SPY",
                        "Stored market data trails the latest expected completed session",
                        {
                            "latest_stored": str(latest_market),
                            "scheduler_completed_session": str(authoritative_market_session),
                        },
                    )
                )
        if str(context.get("market_status", "NEVER_RUN")) == "FAILED":
            conditions.append(
                self._condition(
                    "MARKET_SYNC_FAILED",
                    "WARNING",
                    "MARKET_DATA",
                    "daily-sync",
                    "Daily market-data synchronization most recently failed",
                    {},
                )
            )

        broker_service = AlpacaBrokerSyncService(
            self.session,
            config=self.config,
            now_provider=self.now_provider,
            scheduler_running=bool(context.get("broker_running", False)),
        )
        broker_status = await broker_service.status()
        fresh = bool(
            broker_status.enabled
            and broker_status.configured
            and broker_status.status == BrokerSyncRunStatus.SUCCEEDED.value
            and broker_status.data_age_seconds is not None
            and broker_status.data_age_seconds <= broker_status.interval_seconds * 2
        )
        broker = BrokerOperationsSchema(
            enabled=broker_status.enabled,
            configured=broker_status.configured,
            environment=broker_status.environment,
            status=broker_status.status,
            last_success_at=broker_status.last_success_at,
            data_age_seconds=broker_status.data_age_seconds,
            snapshot_authoritative=fresh,
        )
        if not broker.enabled:
            conditions.append(
                self._condition(
                    "BROKER_SYNC_DISABLED",
                    "INFO",
                    "BROKER",
                    "ALPACA",
                    "Alpaca read-only synchronization is intentionally disabled",
                    {"environment": broker.environment},
                )
            )
        elif not broker.configured:
            conditions.append(
                self._condition(
                    "BROKER_SYNC_MISCONFIGURED",
                    "WARNING",
                    "BROKER",
                    "ALPACA",
                    "Alpaca read-only synchronization is enabled but credentials are incomplete",
                    {"environment": broker.environment},
                )
            )
        else:
            if broker.status == BrokerSyncRunStatus.FAILED.value:
                conditions.append(
                    self._condition(
                        "BROKER_SYNC_FAILED",
                        "WARNING",
                        "BROKER",
                        "ALPACA",
                        "Alpaca read-only synchronization most recently failed",
                        {
                            "last_success_at": broker.last_success_at.isoformat()
                            if broker.last_success_at
                            else None
                        },
                    )
                )
            if not fresh:
                conditions.append(
                    self._condition(
                        "BROKER_SYNC_STALE",
                        "WARNING",
                        "BROKER",
                        "ALPACA",
                        "Alpaca evidence is not fresh enough for authoritative reconciliation",
                        {
                            "data_age_seconds": broker.data_age_seconds,
                            "threshold_seconds": broker_status.interval_seconds * 2,
                        },
                    )
                )
        latest_any_run = await self.session.scalar(
            select(BrokerSyncRun).order_by(BrokerSyncRun.started_at.desc()).limit(1)
        )
        if (
            latest_any_run is not None
            and latest_any_run.environment != self.config.ALPACA_ENVIRONMENT
        ):
            conditions.append(
                self._condition(
                    "BROKER_ENVIRONMENT_MISMATCH",
                    "CRITICAL",
                    "BROKER",
                    "ALPACA",
                    "Latest broker evidence belongs to a different Alpaca environment",
                    {
                        "configured_environment": self.config.ALPACA_ENVIRONMENT,
                        "observed_environment": latest_any_run.environment,
                    },
                )
            )

        expected_buys = expected_sells = overdue = ambiguous = conflicts = 0
        for action in actions:
            action_conditions, is_overdue = self._action_conditions(action, latest_market)
            conditions.extend(action_conditions)
            expected_buys += action.side == "BUY" and action.status.value not in {
                "RECORDED",
                "SKIPPED",
            }
            expected_sells += action.side == "SELL" and action.status.value not in {
                "RECORDED",
                "SKIPPED",
            }
            overdue += is_overdue
            ambiguous += action.broker_match_state == BrokerMatchState.AMBIGUOUS.value
            conflicts += action.broker_match_state == BrokerMatchState.CONFLICT.value

        relevant_symbols = {item.ticker for item in positions} | {item.ticker for item in actions}
        executions = list(
            (
                await self.session.execute(
                    select(BrokerExecution).where(
                        BrokerExecution.environment == self.config.ALPACA_ENVIRONMENT
                    )
                )
            ).scalars()
        )
        unmatched = 0
        for execution in executions:
            if execution.match_state == BrokerMatchState.AMBIGUOUS.value:
                conditions.append(
                    self._condition(
                        "BROKER_MATCH_AMBIGUOUS",
                        "WARNING",
                        "RECONCILIATION",
                        str(execution.id),
                        f"Broker execution for {execution.symbol} has ambiguous Forward matches",
                        {"ticker": execution.symbol, "side": execution.side},
                    )
                )
            elif execution.match_state == BrokerMatchState.UNMATCHED.value:
                unmatched += 1
                conditions.append(
                    self._condition(
                        "UNMATCHED_BROKER_ACTIVITY",
                        "INFO",
                        "BROKER",
                        str(execution.id),
                        f"Unmatched Alpaca activity observed for {execution.symbol}",
                        {
                            "ticker": execution.symbol,
                            "side": execution.side,
                            "forward_related_symbol": execution.symbol in relevant_symbols,
                        },
                    )
                )

        drifts = await self._position_drifts(now, positions, relevant_symbols, fresh)
        for drift in drifts:
            critical = drift.forward_quantity == 0 and drift.broker_quantity > 0
            conditions.append(
                self._condition(
                    "POSITION_QUANTITY_DRIFT",
                    "CRITICAL" if critical else "WARNING",
                    "POSITION",
                    drift.ticker,
                    f"Forward and Alpaca quantities differ for {drift.ticker}",
                    {
                        "ticker": drift.ticker,
                        "forward_quantity": str(drift.forward_quantity),
                        "broker_quantity": str(drift.broker_quantity),
                        "difference": str(drift.difference),
                        "snapshot_authoritative": True,
                    },
                )
            )

        startup = await self._startup_check(context)
        if not startup.schema_compatible:
            conditions.append(
                self._condition(
                    "SCHEMA_MIGRATION_REQUIRED",
                    "CRITICAL",
                    "SYSTEM",
                    "database-schema",
                    "Database schema is not at the Sprint 28 migration head",
                    {
                        "expected": startup.expected_schema_revision,
                        "observed": startup.observed_schema_revision,
                    },
                )
            )
        return OperationsSnapshot(
            evaluated_at=now,
            conditions=conditions,
            forward=forward,
            broker=broker,
            drifts=drifts,
            startup=startup,
            expected_manual_buys=int(expected_buys),
            expected_manual_sells=int(expected_sells),
            overdue_actions=overdue,
            unmatched=unmatched,
            ambiguous=ambiguous,
            conflicts=conflicts,
        )

    def _action_conditions(
        self, action: ExternalActionSchema, latest_market: date | None
    ) -> tuple[list[IncidentCondition], bool]:
        conditions: list[IncidentCondition] = []
        identity = str(action.id)
        done = action.status.value in {"RECORDED", "SKIPPED"}
        due = action.planned_execution_session or action.actual_virtual_execution_session
        overdue = bool(
            not done and latest_market is not None and due is not None and latest_market >= due
        )
        facts = {
            "ticker": action.ticker,
            "side": action.side,
            "expected_session": str(due) if due else None,
            "latest_completed_session": str(latest_market) if latest_market else None,
            "status": action.status.value,
            "reconciliation_status": action.reconciliation_status.value,
        }
        if action.status.value == "AWAITING_ACTION" and not overdue:
            incident_type = (
                "EXTERNAL_BUY_ACTION_UPCOMING"
                if action.side == "BUY"
                else "EXTERNAL_SELL_ACTION_UPCOMING"
            )
            conditions.append(
                self._condition(
                    incident_type,
                    "INFO",
                    "EXTERNAL_EXECUTION",
                    identity,
                    f"Manual {action.side} action for {action.ticker} is upcoming",
                    facts,
                )
            )
        if action.side == "SELL" and not done:
            conditions.append(
                self._condition(
                    "MANUAL_EXIT_ACTION_REQUIRED",
                    "WARNING",
                    "EXTERNAL_EXECUTION",
                    identity,
                    f"Manual exit action is required for {action.ticker}",
                    facts,
                )
            )
            if overdue:
                conditions.append(
                    self._condition(
                        "MANUAL_EXIT_ACTION_OVERDUE",
                        "CRITICAL",
                        "EXTERNAL_EXECUTION",
                        identity,
                        f"Manual exit action is overdue for {action.ticker}",
                        facts,
                    )
                )
        elif overdue:
            conditions.append(
                self._condition(
                    "EXTERNAL_ACTION_OVERDUE",
                    "WARNING",
                    "EXTERNAL_EXECUTION",
                    identity,
                    f"Manual BUY execution record is overdue for {action.ticker}",
                    facts,
                )
            )
        elif action.status.value == "AWAITING_RECORD":
            conditions.append(
                self._condition(
                    "EXTERNAL_ACTION_AWAITING_RECORD",
                    "INFO",
                    "EXTERNAL_EXECUTION",
                    identity,
                    f"External execution record is awaited for {action.ticker}",
                    facts,
                )
            )
        if action.status.value == "PARTIALLY_RECORDED":
            conditions.append(
                self._condition(
                    "PARTIAL_EXTERNAL_EXECUTION",
                    "WARNING" if action.side == "SELL" else "INFO",
                    "EXTERNAL_EXECUTION",
                    identity,
                    f"External {action.side} execution is partially recorded for {action.ticker}",
                    facts,
                )
            )
        if action.status.value == "SKIPPED":
            conditions.append(
                self._condition(
                    "SKIPPED_EXTERNAL_EXECUTION",
                    "INFO",
                    "EXTERNAL_EXECUTION",
                    identity,
                    f"External {action.side} execution was intentionally skipped "
                    f"for {action.ticker}",
                    facts,
                )
            )
        recon_map = {
            "EXECUTED_AFTER_VIRTUAL_CANCEL": ("EXECUTED_AFTER_VIRTUAL_CANCEL", "CRITICAL"),
            "QUANTITY_DIVERGENCE": ("QUANTITY_DIVERGENCE", "WARNING"),
            "PRICE_DIVERGENCE": ("PRICE_DIVERGENCE", "WARNING"),
            "PRICE_AND_QUANTITY_DIVERGENCE": ("QUANTITY_DIVERGENCE", "WARNING"),
            "BROKER_CONFLICT": (
                "BROKER_EXECUTION_CONFLICT",
                "CRITICAL" if action.side == "SELL" else "WARNING",
            ),
        }
        mapped = recon_map.get(action.reconciliation_status.value)
        if mapped is not None:
            incident_type, severity = mapped
            if incident_type != "PRICE_DIVERGENCE" or abs(
                action.price_difference_bps or Decimal("0")
            ) >= Decimal("25"):
                conditions.append(
                    self._condition(
                        incident_type,
                        severity,
                        "RECONCILIATION",
                        identity,
                        f"Execution reconciliation requires review for {action.ticker}",
                        facts
                        | {
                            "price_difference_bps": str(action.price_difference_bps)
                            if action.price_difference_bps is not None
                            else None,
                            "quantity_difference": str(action.share_variance_vs_virtual)
                            if action.share_variance_vs_virtual is not None
                            else None,
                        },
                    )
                )
        return conditions, overdue

    async def _position_drifts(
        self,
        now: datetime,
        positions: list[ForwardPosition],
        relevant_symbols: set[str],
        fresh: bool,
    ) -> list[PositionDriftSchema]:
        if not fresh or not relevant_symbols:
            return []
        run = await self.session.scalar(
            select(BrokerSyncRun)
            .where(
                BrokerSyncRun.environment == self.config.ALPACA_ENVIRONMENT,
                BrokerSyncRun.status == BrokerSyncRunStatus.SUCCEEDED.value,
            )
            .order_by(BrokerSyncRun.completed_at.desc())
            .limit(1)
        )
        if run is None:
            return []
        broker_rows = list(
            (
                await self.session.execute(
                    select(BrokerPositionSnapshot).where(
                        BrokerPositionSnapshot.sync_run_id == run.id,
                        BrokerPositionSnapshot.symbol.in_(relevant_symbols),
                    )
                )
            ).scalars()
        )
        broker_by_symbol = {item.symbol: Decimal(item.quantity) for item in broker_rows}
        forward_by_symbol: dict[str, Decimal] = {}
        for item in positions:
            if item.status == ForwardPositionStatus.OPEN.value:
                forward_by_symbol[item.ticker] = Decimal(item.shares)
            else:
                forward_by_symbol.setdefault(item.ticker, Decimal("0"))
        drifts: list[PositionDriftSchema] = []
        for ticker in sorted(relevant_symbols):
            forward_quantity = forward_by_symbol.get(ticker, Decimal("0"))
            broker_quantity = broker_by_symbol.get(ticker, Decimal("0"))
            if forward_quantity != broker_quantity:
                drifts.append(
                    PositionDriftSchema(
                        ticker=ticker,
                        forward_quantity=forward_quantity,
                        broker_quantity=broker_quantity,
                        difference=broker_quantity - forward_quantity,
                        evaluated_at=now,
                    )
                )
        return drifts

    async def _startup_check(self, context: dict[str, Any]) -> StartupCheckSchema:
        observed: str | None = None
        reachable = True
        try:
            observed = await self.session.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            reachable = False
        configured = bool(self.config.ALPACA_API_KEY and self.config.ALPACA_SECRET_KEY)
        broker_state = (
            "DISABLED"
            if not self.config.ALPACA_SYNC_ENABLED
            else "CONFIGURED"
            if configured
            else "MISCONFIGURED"
        )
        return StartupCheckSchema(
            database_reachable=reachable,
            schema_compatible=observed == EXPECTED_SCHEMA_REVISION,
            expected_schema_revision=EXPECTED_SCHEMA_REVISION,
            observed_schema_revision=observed,
            forward_scheduler_initialized=bool(context.get("forward_initialized", True)),
            broker_configuration_state=broker_state,
            operations_monitor_initialized=bool(context.get("operations_initialized", True)),
        )

    async def _schema(
        self, row: OperationalIncident, *, include_events: bool
    ) -> OperationalIncidentSchema:
        events: list[OperationalIncidentEventSchema] = []
        if include_events:
            event_rows = list(
                (
                    await self.session.execute(
                        select(OperationalIncidentEvent)
                        .where(OperationalIncidentEvent.incident_id == row.id)
                        .order_by(OperationalIncidentEvent.created_at)
                    )
                ).scalars()
            )
            events = [OperationalIncidentEventSchema.model_validate(event) for event in event_rows]
        return OperationalIncidentSchema.model_validate(row).model_copy(update={"events": events})

    def _event(
        self,
        row: OperationalIncident,
        event_type: OperationalEventType,
        from_status: OperationalIncidentStatus | None,
        to_status: OperationalIncidentStatus,
        reason: str,
        evidence: dict[str, Any],
        created_at: datetime,
        *,
        source: str = "OPERATIONS_MONITOR",
    ) -> None:
        self.session.add(
            OperationalIncidentEvent(
                incident_id=row.id,
                event_type=event_type.value,
                from_status=from_status.value if from_status else None,
                to_status=to_status.value,
                source=source,
                reason=reason,
                evidence=evidence,
                created_at=created_at,
            )
        )

    @staticmethod
    def _condition(
        incident_type: str,
        severity: str,
        domain: str,
        identity: str,
        summary: str,
        evidence: dict[str, Any],
    ) -> IncidentCondition:
        return IncidentCondition(
            OperationalIncidentType(incident_type),
            OperationalSeverity(severity),
            OperationalSourceDomain(domain),
            identity,
            summary,
            evidence,
        )

    @staticmethod
    def _overall(conditions: list[IncidentCondition]) -> OperationalHealth:
        severities = {item.severity for item in conditions}
        return OperationsMonitor._health_from_counts(
            OperationalSeverity.CRITICAL in severities, OperationalSeverity.WARNING in severities
        )

    @staticmethod
    def _health_from_counts(critical: int, warning: int) -> OperationalHealth:
        if critical:
            return OperationalHealth.DEGRADED
        if warning:
            return OperationalHealth.ATTENTION
        return OperationalHealth.HEALTHY
