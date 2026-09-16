from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from conftest import TestSessionLocal
from sqlalchemy import func, select

from alphapilot.core.config import Settings
from alphapilot.database.models.broker_sync import (
    BrokerPositionSnapshot,
    BrokerSyncRun,
    BrokerSyncRunStatus,
)
from alphapilot.database.models.external_execution import (
    ExternalActionStatus,
    ExternalReconciliationStatus,
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
from alphapilot.schemas.external_execution import ExternalActionSchema
from alphapilot.schemas.operations import (
    BrokerOperationsSchema,
    ForwardOperationsSchema,
    StartupCheckSchema,
)
from alphapilot.services.operations_monitor import (
    IncidentCondition,
    OperationsIncidentConflictError,
    OperationsMonitor,
    OperationsSnapshot,
)

NOW = datetime(2026, 9, 15, 17, 0, tzinfo=UTC)


def snapshot(*conditions: IncidentCondition) -> OperationsSnapshot:
    return OperationsSnapshot(
        evaluated_at=NOW,
        conditions=list(conditions),
        forward=ForwardOperationsSchema(
            status="ACTIVE",
            scheduler_status="SUCCEEDED",
            scheduler_running=True,
            cash=Decimal("50000"),
            equity=Decimal("100000"),
            open_positions=1,
            pending_sessions=0,
            latest_processed_session=date(2026, 9, 14),
            latest_completed_market_session=date(2026, 9, 14),
        ),
        broker=BrokerOperationsSchema(
            enabled=True,
            configured=True,
            environment="PAPER",
            status="SUCCEEDED",
            last_success_at=NOW,
            data_age_seconds=0,
            snapshot_authoritative=True,
        ),
        drifts=[],
        startup=StartupCheckSchema(
            database_reachable=True,
            schema_compatible=True,
            expected_schema_revision="c28a0f1b2d3e",
            observed_schema_revision="c28a0f1b2d3e",
            forward_scheduler_initialized=True,
            broker_configuration_state="CONFIGURED",
            operations_monitor_initialized=True,
        ),
    )


def condition(
    severity: OperationalSeverity = OperationalSeverity.WARNING,
) -> IncidentCondition:
    return IncidentCondition(
        OperationalIncidentType.FORWARD_ENGINE_STALE,
        severity,
        OperationalSourceDomain.FORWARD,
        "portfolio-1",
        "Forward engine is stale",
        {"pending_sessions": 1},
    )


@pytest.mark.asyncio
async def test_healthy_when_no_active_conditions(db_session, monkeypatch) -> None:
    monitor = OperationsMonitor(db_session)
    monkeypatch.setattr(monitor, "_snapshot", lambda: asyncio.sleep(0, result=snapshot()))
    result = await monitor.evaluate()
    assert result.overall_health == OperationalHealth.HEALTHY
    assert result.opened == 0


@pytest.mark.asyncio
async def test_repeated_evaluation_deduplicates_without_event_spam(db_session, monkeypatch) -> None:
    monitor = OperationsMonitor(db_session)
    current = snapshot(condition())
    monkeypatch.setattr(monitor, "_snapshot", lambda: asyncio.sleep(0, result=current))

    results = [await monitor.evaluate() for _ in range(20)]

    assert results[0].opened == 1
    assert all(result.opened == 0 and result.updated == 0 for result in results[1:])
    assert await db_session.scalar(select(func.count()).select_from(OperationalIncident)) == 1
    assert await db_session.scalar(select(func.count()).select_from(OperationalIncidentEvent)) == 1


@pytest.mark.asyncio
async def test_acknowledge_does_not_resolve_and_clear_then_recurrence_is_new_occurrence(
    db_session, monkeypatch
) -> None:
    monitor = OperationsMonitor(db_session)
    current = snapshot(condition())
    monkeypatch.setattr(monitor, "_snapshot", lambda: asyncio.sleep(0, result=current))
    await monitor.evaluate()
    first = (await monitor.list_incidents())[0]

    acknowledged = await monitor.acknowledge(first.id, "Operator is investigating")
    assert acknowledged.status == OperationalIncidentStatus.ACKNOWLEDGED
    assert OperationalEventType.ACKNOWLEDGED in {event.event_type for event in acknowledged.events}
    await monitor.evaluate()
    assert (await monitor.incident(first.id)).status == OperationalIncidentStatus.ACKNOWLEDGED

    current = snapshot()
    await monitor.evaluate()
    resolved = await monitor.incident(first.id)
    assert resolved.status == OperationalIncidentStatus.RESOLVED
    with pytest.raises(OperationsIncidentConflictError):
        await monitor.acknowledge(first.id, "Too late")

    current = snapshot(condition())
    await monitor.evaluate()
    rows = await monitor.list_incidents()
    assert len(rows) == 2
    assert {item.occurrence for item in rows} == {1, 2}


@pytest.mark.asyncio
async def test_material_change_adds_one_update_event(db_session, monkeypatch) -> None:
    monitor = OperationsMonitor(db_session)
    current = snapshot(condition())
    monkeypatch.setattr(monitor, "_snapshot", lambda: asyncio.sleep(0, result=current))
    await monitor.evaluate()
    current = snapshot(condition(OperationalSeverity.CRITICAL))
    result = await monitor.evaluate()
    incident = (await monitor.list_incidents(active_only=True))[0]
    detail = await monitor.incident(incident.id)
    assert result.updated == 1
    assert [event.event_type for event in detail.events] == [
        OperationalEventType.OPENED,
        OperationalEventType.UPDATED,
    ]


@pytest.mark.asyncio
async def test_concurrent_evaluations_share_one_active_incident(monkeypatch) -> None:
    async with TestSessionLocal() as first_session, TestSessionLocal() as second_session:
        first = OperationsMonitor(first_session)
        second = OperationsMonitor(second_session)
        current = snapshot(condition())
        monkeypatch.setattr(first, "_snapshot", lambda: asyncio.sleep(0, result=current))
        monkeypatch.setattr(second, "_snapshot", lambda: asyncio.sleep(0, result=current))
        await asyncio.gather(first.evaluate(), second.evaluate())
    async with TestSessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(OperationalIncident)) == 1


def action(*, side: str, status: str, due: date, reconciliation: str = "INCOMPLETE"):
    return ExternalActionSchema.model_construct(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        side=side,
        ticker="APA",
        status=ExternalActionStatus(status),
        reconciliation_status=ExternalReconciliationStatus(reconciliation),
        planned_execution_session=due,
        actual_virtual_execution_session=None,
        broker_match_state=None,
        price_difference_bps=None,
        share_variance_vs_virtual=None,
    )


def test_action_deadlines_use_completed_session_and_exit_is_critical() -> None:
    monitor = OperationsMonitor(
        None,  # type: ignore[arg-type]
        now_provider=lambda: NOW,
        config=Settings(DEBUG=False),
    )
    future = action(side="BUY", status="AWAITING_ACTION", due=date(2026, 9, 16))
    upcoming, overdue = monitor._action_conditions(future, date(2026, 9, 15))
    assert not overdue
    assert upcoming[0].incident_type == OperationalIncidentType.EXTERNAL_BUY_ACTION_UPCOMING

    exit_action = action(side="SELL", status="AWAITING_RECORD", due=date(2026, 9, 15))
    exit_conditions, overdue = monitor._action_conditions(exit_action, date(2026, 9, 15))
    assert overdue
    critical = [
        item
        for item in exit_conditions
        if item.incident_type == OperationalIncidentType.MANUAL_EXIT_ACTION_OVERDUE
    ]
    assert critical[0].severity == OperationalSeverity.CRITICAL


def test_clock_time_alone_does_not_make_action_overdue() -> None:
    monitor = OperationsMonitor(None, now_provider=lambda: NOW)  # type: ignore[arg-type]
    item = action(side="BUY", status="AWAITING_RECORD", due=date(2026, 9, 16))
    conditions, overdue = monitor._action_conditions(item, date(2026, 9, 15))
    assert not overdue
    assert all(
        condition.incident_type != OperationalIncidentType.EXTERNAL_ACTION_OVERDUE
        for condition in conditions
    )


@pytest.mark.parametrize(
    ("status", "reconciliation", "expected_type", "severity"),
    [
        ("AWAITING_RECORD", "INCOMPLETE", "EXTERNAL_ACTION_AWAITING_RECORD", "INFO"),
        ("PARTIALLY_RECORDED", "PARTIAL", "PARTIAL_EXTERNAL_EXECUTION", "INFO"),
        ("SKIPPED", "SKIPPED", "SKIPPED_EXTERNAL_EXECUTION", "INFO"),
        (
            "RECORDED",
            "EXECUTED_AFTER_VIRTUAL_CANCEL",
            "EXECUTED_AFTER_VIRTUAL_CANCEL",
            "CRITICAL",
        ),
        ("RECORDED", "QUANTITY_DIVERGENCE", "QUANTITY_DIVERGENCE", "WARNING"),
    ],
)
def test_external_action_reconciliation_incident_mapping(
    status: str, reconciliation: str, expected_type: str, severity: str
) -> None:
    monitor = OperationsMonitor(None, now_provider=lambda: NOW)  # type: ignore[arg-type]
    item = action(
        side="BUY",
        status=status,
        due=date(2026, 9, 16),
        reconciliation=reconciliation,
    )
    conditions, _ = monitor._action_conditions(item, date(2026, 9, 15))
    match = next(condition for condition in conditions if condition.incident_type == expected_type)
    assert match.severity == severity


def test_entry_conflict_is_warning_and_exit_conflict_is_critical() -> None:
    monitor = OperationsMonitor(None, now_provider=lambda: NOW)  # type: ignore[arg-type]
    entry, _ = monitor._action_conditions(
        action(
            side="BUY",
            status="RECORDED",
            due=date(2026, 9, 15),
            reconciliation="BROKER_CONFLICT",
        ),
        date(2026, 9, 15),
    )
    exit_conditions, _ = monitor._action_conditions(
        action(
            side="SELL",
            status="RECORDED",
            due=date(2026, 9, 15),
            reconciliation="BROKER_CONFLICT",
        ),
        date(2026, 9, 15),
    )
    assert entry[-1].severity == OperationalSeverity.WARNING
    assert exit_conditions[-1].severity == OperationalSeverity.CRITICAL


def test_overall_health_ignores_info_and_escalates_warning_then_critical() -> None:
    info = IncidentCondition(
        OperationalIncidentType.BROKER_SYNC_DISABLED,
        OperationalSeverity.INFO,
        OperationalSourceDomain.BROKER,
        "ALPACA",
        "disabled",
    )
    assert OperationsMonitor._overall([info]) == OperationalHealth.HEALTHY
    assert OperationsMonitor._overall([condition()]) == OperationalHealth.ATTENTION
    assert (
        OperationsMonitor._overall([condition(OperationalSeverity.CRITICAL)])
        == OperationalHealth.DEGRADED
    )


@pytest.mark.asyncio
async def test_position_drift_uses_fresh_snapshot_and_missing_symbol_means_zero(
    db_session,
) -> None:
    config = Settings(
        DEBUG=False,
        ALPACA_SYNC_ENABLED=True,
        ALPACA_API_KEY="test-key",
        ALPACA_SECRET_KEY="test-secret",
    )
    run = BrokerSyncRun(
        provider="ALPACA",
        environment="PAPER",
        status=BrokerSyncRunStatus.SUCCEEDED.value,
        started_at=NOW,
        completed_at=NOW,
        requested_after=NOW,
        position_count=1,
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        BrokerPositionSnapshot(
            sync_run_id=run.id,
            provider="ALPACA",
            environment="PAPER",
            symbol="CLOSED",
            side="long",
            quantity=Decimal("7"),
            observed_at=NOW,
        )
    )
    await db_session.commit()
    positions = [
        SimpleNamespace(ticker="OPEN", status="OPEN", shares=100),
        SimpleNamespace(ticker="CLOSED", status="CLOSED", shares=100),
    ]
    monitor = OperationsMonitor(db_session, config=config, now_provider=lambda: NOW)
    drifts = await monitor._position_drifts(
        NOW,
        positions,  # type: ignore[arg-type]
        {"OPEN", "CLOSED"},
        True,
    )
    by_ticker = {drift.ticker: drift for drift in drifts}
    assert by_ticker["OPEN"].broker_quantity == 0
    assert by_ticker["OPEN"].difference == -100
    assert by_ticker["CLOSED"].forward_quantity == 0
    assert by_ticker["CLOSED"].broker_quantity == 7
    assert (
        await monitor._position_drifts(
            NOW,
            positions,  # type: ignore[arg-type]
            {"OPEN", "CLOSED"},
            False,
        )
        == []
    )
