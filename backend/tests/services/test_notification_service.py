from __future__ import annotations

import asyncio
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from conftest import TestSessionLocal
from sqlalchemy import func, select

from alphapilot.core.config import Settings
from alphapilot.database.models.notifications import (
    Notification,
    NotificationAttemptResult,
    NotificationDeliveryAttempt,
    NotificationFailureCategory,
    NotificationKind,
    NotificationPreference,
    NotificationStatus,
)
from alphapilot.database.models.operations import (
    OperationalEventType,
    OperationalIncident,
    OperationalIncidentEvent,
    OperationalIncidentStatus,
    OperationalIncidentType,
    OperationalSeverity,
    OperationalSourceDomain,
)
from alphapilot.notifications.email import NotificationSendResult
from alphapilot.schemas.notifications import NotificationPreferenceUpdate
from alphapilot.schemas.operations import (
    BrokerOperationsSchema,
    DailyOperationsSummarySchema,
    ForwardOperationsSchema,
)
from alphapilot.services.notifications import NotificationDeliveryWorker, NotificationService

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def configured_settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "DEBUG": False,
        "NOTIFICATIONS_ENABLED": True,
        "NOTIFICATION_EMAIL_ENABLED": True,
        "SMTP_HOST": "smtp.test",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "operator",
        "SMTP_PASSWORD": "secret-test-value",
        "NOTIFICATION_FROM_EMAIL": "alphapilot@example.com",
        "NOTIFICATION_EMAIL_TO": "operator@example.com",
    }
    values.update(updates)
    return Settings(**values)


async def enable_preferences(db_session, *, daily: bool = False) -> None:
    await NotificationService(db_session, config=configured_settings()).update_preference(
        NotificationPreferenceUpdate(
            notifications_enabled=True,
            email_enabled=True,
            recipient="operator@example.com",
            warning_enabled=True,
            critical_enabled=True,
            recovery_enabled=True,
            daily_summary_enabled=daily,
        )
    )


async def add_incident(
    db_session,
    *,
    incident_type: OperationalIncidentType = OperationalIncidentType.FORWARD_ENGINE_STALE,
    severity: OperationalSeverity = OperationalSeverity.WARNING,
    source: OperationalSourceDomain = OperationalSourceDomain.FORWARD,
    evidence: dict[str, object] | None = None,
) -> tuple[OperationalIncident, OperationalIncidentEvent]:
    incident = OperationalIncident(
        incident_type=incident_type.value,
        severity=severity.value,
        status=OperationalIncidentStatus.OPEN.value,
        source_domain=source.value,
        source_identity="source-1",
        deduplication_key=f"{incident_type.value}:{source.value}:source-1",
        active_deduplication_key=f"{incident_type.value}:{source.value}:source-1",
        occurrence=1,
        opened_at=NOW,
        last_observed_at=NOW,
        summary="Forward engine is stale",
        evidence=evidence or {},
    )
    db_session.add(incident)
    await db_session.flush()
    event = OperationalIncidentEvent(
        incident_id=incident.id,
        event_type=OperationalEventType.OPENED.value,
        from_status=None,
        to_status=OperationalIncidentStatus.OPEN.value,
        source="TEST",
        reason="Synthetic incident",
        evidence=incident.evidence,
        created_at=NOW,
    )
    db_session.add(event)
    await db_session.flush()
    return incident, event


class FakeNotificationProvider:
    def __init__(self, results: list[NotificationSendResult] | None = None) -> None:
        self.results = results or [NotificationSendResult(delivered=True)]
        self.calls = 0
        self.subjects: list[str] = []
        self._lock = threading.Lock()

    def send(self, notification: Notification) -> NotificationSendResult:
        with self._lock:
            self.calls += 1
            self.subjects.append(notification.subject)
            return self.results[min(self.calls - 1, len(self.results) - 1)]


@pytest.mark.asyncio
async def test_disabled_and_info_policies_create_no_outbox(db_session) -> None:
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    disabled = NotificationService(
        db_session,
        config=configured_settings(NOTIFICATIONS_ENABLED=False),
        now_provider=lambda: NOW,
    )
    assert await disabled.plan_incident_transition(incident, event, transition="OPENED") is None

    await enable_preferences(db_session)
    incident.severity = OperationalSeverity.INFO.value
    assert (
        await NotificationService(
            db_session, config=configured_settings(), now_provider=lambda: NOW
        ).plan_incident_transition(incident, event, transition="OPENED")
        is None
    )
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 0


@pytest.mark.asyncio
async def test_enabling_preferences_backfills_one_active_critical(db_session) -> None:
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    service = NotificationService(
        db_session, config=configured_settings(), now_provider=lambda: NOW
    )
    assert await service.plan_incident_transition(incident, event, transition="OPENED") is None
    await enable_preferences(db_session)
    assert await service.plan_active_incidents() == 1
    assert await service.plan_active_incidents() == 0


@pytest.mark.asyncio
async def test_warning_critical_dedup_and_safe_exit_content(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.MANUAL_EXIT_ACTION_REQUIRED,
        severity=OperationalSeverity.WARNING,
        source=OperationalSourceDomain.EXTERNAL_EXECUTION,
        evidence={
            "ticker": "HAL",
            "side": "SELL",
            "shares": 20,
            "expected_session": "2026-09-16",
            "reason": "SMA150_COMPLETED_CLOSE_EXIT",
        },
    )
    service = NotificationService(
        db_session, config=configured_settings(), now_provider=lambda: NOW
    )
    first = await service.plan_incident_transition(incident, event, transition="OPENED")
    duplicate = await service.plan_incident_transition(incident, event, transition="OPENED")
    assert first is not None
    assert duplicate is None
    assert "Manual broker SELL action required" in first.body_text
    assert "has not submitted, cancelled, or executed" in first.body_text
    assert "Shares: 20" in first.body_text
    assert "secret-test-value" not in first.body_text
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 1


@pytest.mark.asyncio
async def test_live_and_paper_broker_labels_are_explicit(db_session) -> None:
    await enable_preferences(db_session)
    live_incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
        evidence={"environment": "LIVE"},
    )
    live = await NotificationService(
        db_session, config=configured_settings(ALPACA_ENVIRONMENT="LIVE"), now_provider=lambda: NOW
    ).plan_incident_transition(live_incident, event, transition="OPENED")
    assert live is not None
    assert "[LIVE]" in live.subject
    assert "LIVE ACCOUNT OBSERVATION" in live.body_text

    live_incident.id = live_incident.id
    live_incident.evidence = {"environment": "PAPER"}
    paper = await NotificationService(
        db_session, config=configured_settings(), now_provider=lambda: NOW
    ).plan_incident_transition(live_incident, event, transition="ESCALATED")
    assert paper is not None
    assert "Environment: PAPER" in paper.body_text


@pytest.mark.asyncio
async def test_transient_retry_backoff_attempt_audit_and_success(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    clock = [NOW]
    config = configured_settings()
    service = NotificationService(db_session, config=config, now_provider=lambda: clock[0])
    row = await service.plan_incident_transition(incident, event, transition="OPENED")
    await db_session.commit()
    assert row is not None
    provider = FakeNotificationProvider(
        [
            NotificationSendResult(
                delivered=False, failure_category=NotificationFailureCategory.CONNECTION
            ),
            NotificationSendResult(
                delivered=False, failure_category=NotificationFailureCategory.TIMEOUT
            ),
            NotificationSendResult(delivered=True, provider_message_reference="smtp-test-1"),
        ]
    )
    worker = NotificationDeliveryWorker(
        db_session, provider, config=config, now_provider=lambda: clock[0]
    )
    assert await worker.run_pending() == 0
    await db_session.refresh(row)
    assert row.status == NotificationStatus.RETRY_PENDING.value
    assert row.next_attempt_at == NOW + timedelta(seconds=60)
    clock[0] += timedelta(seconds=60)
    assert await worker.run_pending() == 0
    await db_session.refresh(row)
    assert row.next_attempt_at == NOW + timedelta(seconds=360)
    clock[0] = row.next_attempt_at
    assert await worker.run_pending() == 1
    await db_session.refresh(row)
    assert row.status == NotificationStatus.DELIVERED.value
    attempts = list(
        (
            await db_session.execute(
                select(NotificationDeliveryAttempt).order_by(
                    NotificationDeliveryAttempt.attempt_number
                )
            )
        ).scalars()
    )
    assert [item.result for item in attempts] == [
        NotificationAttemptResult.TRANSIENT_FAILURE.value,
        NotificationAttemptResult.TRANSIENT_FAILURE.value,
        NotificationAttemptResult.DELIVERED.value,
    ]


@pytest.mark.asyncio
async def test_permanent_failure_and_manual_retry_use_durable_path(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    config = configured_settings()
    service = NotificationService(db_session, config=config, now_provider=lambda: NOW)
    row = await service.plan_incident_transition(incident, event, transition="OPENED")
    await db_session.commit()
    assert row is not None
    failed = FakeNotificationProvider(
        [
            NotificationSendResult(
                delivered=False,
                permanent=True,
                failure_category=NotificationFailureCategory.AUTHENTICATION,
            )
        ]
    )
    await NotificationDeliveryWorker(
        db_session, failed, config=config, now_provider=lambda: NOW
    ).run_pending()
    await db_session.refresh(row)
    assert row.status == NotificationStatus.FAILED.value
    await service.retry(row.id)
    delivered = FakeNotificationProvider([NotificationSendResult(delivered=True)])
    assert (
        await NotificationDeliveryWorker(
            db_session, delivered, config=config, now_provider=lambda: NOW
        ).run_pending()
        == 1
    )
    assert delivered.calls == 1


@pytest.mark.asyncio
async def test_critical_reminder_ack_suppression_and_one_recovery(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.MANUAL_EXIT_ACTION_OVERDUE,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.EXTERNAL_EXECUTION,
        evidence={"ticker": "HAL", "side": "SELL"},
    )
    clock = [NOW]
    config = configured_settings(NOTIFICATION_CRITICAL_REMINDER_SECONDS=3600)
    service = NotificationService(db_session, config=config, now_provider=lambda: clock[0])
    initial = await service.plan_incident_transition(incident, event, transition="OPENED")
    assert initial is not None
    initial.status = NotificationStatus.DELIVERED.value
    initial.sent_at = NOW
    await db_session.commit()
    clock[0] += timedelta(seconds=3599)
    assert await service.plan_critical_reminders() == 0
    clock[0] += timedelta(seconds=1)
    assert await service.plan_critical_reminders() == 1
    assert await service.plan_critical_reminders() == 0

    reminder = await db_session.scalar(
        select(Notification).where(Notification.kind == NotificationKind.REMINDER.value)
    )
    assert reminder is not None
    assert await service.cancel_pending_for_incident(incident.id, reminders_only=True) == 1
    assert reminder.status == NotificationStatus.CANCELLED.value
    incident.status = OperationalIncidentStatus.ACKNOWLEDGED.value
    await db_session.commit()
    clock[0] += timedelta(hours=1)
    assert await service.plan_critical_reminders() == 0

    incident.status = OperationalIncidentStatus.RESOLVED.value
    incident.active_deduplication_key = None
    incident.resolved_at = clock[0]
    recovery_event = OperationalIncidentEvent(
        incident_id=incident.id,
        event_type=OperationalEventType.RESOLVED.value,
        from_status=OperationalIncidentStatus.ACKNOWLEDGED.value,
        to_status=OperationalIncidentStatus.RESOLVED.value,
        source="TEST",
        reason="Condition cleared",
        evidence={},
        created_at=clock[0],
    )
    db_session.add(recovery_event)
    await db_session.flush()
    recovery = await service.plan_incident_transition(
        incident, recovery_event, transition="RESOLVED"
    )
    duplicate = await service.plan_incident_transition(
        incident, recovery_event, transition="RESOLVED"
    )
    assert recovery is not None and recovery.kind == NotificationKind.RECOVERY.value
    assert duplicate is None


@pytest.mark.asyncio
async def test_notification_incident_never_recurses(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.NOTIFICATION_DELIVERY_FAILED,
        severity=OperationalSeverity.WARNING,
        source=OperationalSourceDomain.NOTIFICATION,
    )
    service = NotificationService(
        db_session, config=configured_settings(), now_provider=lambda: NOW
    )
    assert await service.plan_incident_transition(incident, event, transition="OPENED") is None


@pytest.mark.asyncio
async def test_concurrent_workers_claim_one_provider_call(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    config = configured_settings()
    await NotificationService(
        db_session, config=config, now_provider=lambda: NOW
    ).plan_incident_transition(incident, event, transition="OPENED")
    await db_session.commit()
    provider = FakeNotificationProvider([NotificationSendResult(delivered=True)])

    async def run_worker() -> int:
        async with TestSessionLocal() as session:
            return await NotificationDeliveryWorker(
                session, provider, config=config, now_provider=lambda: NOW
            ).run_pending()

    results = await asyncio.gather(run_worker(), run_worker())
    assert sum(results) == 1
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_expired_delivery_lease_resumes_after_worker_restart(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    config = configured_settings()
    row = await NotificationService(
        db_session, config=config, now_provider=lambda: NOW
    ).plan_incident_transition(incident, event, transition="OPENED")
    assert row is not None
    row.status = NotificationStatus.DELIVERING.value
    row.attempt_count = 1
    row.lease_expires_at = NOW - timedelta(seconds=1)
    row.next_attempt_at = NOW
    await db_session.commit()
    provider = FakeNotificationProvider([NotificationSendResult(delivered=True)])
    delivered = await NotificationDeliveryWorker(
        db_session, provider, config=config, now_provider=lambda: NOW
    ).run_pending()
    await db_session.refresh(row)
    assert delivered == 1
    assert row.status == NotificationStatus.DELIVERED.value
    assert row.attempt_count == 2


@pytest.mark.asyncio
async def test_maximum_five_attempts_and_exact_backoff_schedule(db_session) -> None:
    await enable_preferences(db_session)
    incident, event = await add_incident(
        db_session,
        incident_type=OperationalIncidentType.BROKER_ENVIRONMENT_MISMATCH,
        severity=OperationalSeverity.CRITICAL,
        source=OperationalSourceDomain.BROKER,
    )
    config = configured_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    clock = [NOW]
    row = await NotificationService(
        db_session, config=config, now_provider=lambda: clock[0]
    ).plan_incident_transition(incident, event, transition="OPENED")
    await db_session.commit()
    assert row is not None
    provider = FakeNotificationProvider(
        [
            NotificationSendResult(
                delivered=False, failure_category=NotificationFailureCategory.CONNECTION
            )
        ]
    )
    worker = NotificationDeliveryWorker(
        db_session, provider, config=config, now_provider=lambda: clock[0]
    )
    observed_delays: list[int] = []
    for _ in range(5):
        await worker.run_pending()
        await db_session.refresh(row)
        if row.status == NotificationStatus.RETRY_PENDING.value:
            delay = int((row.next_attempt_at - clock[0]).total_seconds())
            observed_delays.append(delay)
            clock[0] = row.next_attempt_at
    assert observed_delays == [60, 300, 900, 1800]
    assert row.attempt_count == 5
    assert row.status == NotificationStatus.FAILED.value


@pytest.mark.asyncio
async def test_daily_summary_is_once_per_recipient_session(db_session) -> None:
    await enable_preferences(db_session, daily=True)
    service = NotificationService(
        db_session, config=configured_settings(), now_provider=lambda: NOW
    )
    summary = DailyOperationsSummarySchema(
        generated_at=NOW,
        overall_health="ATTENTION",
        critical_count=0,
        warning_count=2,
        forward=ForwardOperationsSchema(
            status="ACTIVE",
            scheduler_status="SUCCEEDED",
            scheduler_running=True,
            cash=Decimal("50000"),
            equity=Decimal("101000"),
            open_positions=2,
            pending_sessions=0,
            latest_processed_session=date(2026, 9, 15),
            latest_completed_market_session=date(2026, 9, 15),
        ),
        expected_manual_buys=1,
        expected_manual_sells=1,
        overdue_actions=0,
        broker=BrokerOperationsSchema(
            enabled=True,
            configured=True,
            environment="PAPER",
            status="SUCCEEDED",
            last_success_at=NOW,
            data_age_seconds=10,
            snapshot_authoritative=True,
        ),
        unmatched_broker_activity=0,
        ambiguous_matches=0,
        execution_conflicts=1,
        position_drift_count=0,
        latest_completed_market_session=date(2026, 9, 15),
        latest_forward_processed_session=date(2026, 9, 15),
    )
    assert await service.plan_daily_summary(summary) is not None
    assert await service.plan_daily_summary(summary) is None
    rows = await service.list_notifications()
    assert len(rows) == 1
    assert rows[0].trading_session == date(2026, 9, 15)


@pytest.mark.asyncio
async def test_preference_singleton_and_status_have_no_credentials(db_session) -> None:
    await enable_preferences(db_session)
    service = NotificationService(
        db_session,
        config=configured_settings(),
        now_provider=lambda: NOW,
        worker_running=True,
    )
    status = await service.status()
    assert status.enabled is True
    assert status.email_enabled is True
    assert status.configured is True
    assert status.worker_running is True
    assert "password" not in status.model_dump()
    assert await db_session.scalar(select(func.count()).select_from(NotificationPreference)) == 1
