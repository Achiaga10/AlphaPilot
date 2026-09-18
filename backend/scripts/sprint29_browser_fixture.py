"""Seed or deliver isolated TEST-database evidence for Sprint 29 browser acceptance."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from alphapilot.core.config import Settings, settings
from alphapilot.database.models.notifications import Notification
from alphapilot.database.models.operations import (
    OperationalEventType,
    OperationalIncident,
    OperationalIncidentEvent,
    OperationalIncidentStatus,
    OperationalIncidentType,
    OperationalSeverity,
    OperationalSourceDomain,
)
from alphapilot.database.session import AsyncSessionLocal
from alphapilot.notifications.email import NotificationSendResult
from alphapilot.schemas.notifications import NotificationPreferenceUpdate
from alphapilot.schemas.operations import (
    BrokerOperationsSchema,
    DailyOperationsSummarySchema,
    ForwardOperationsSchema,
)
from alphapilot.services.notifications import NotificationDeliveryWorker, NotificationService

NOW = datetime(2026, 9, 16, 20, 0, tzinfo=UTC)
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CONFIG = Settings(
    DEBUG=False,
    NOTIFICATIONS_ENABLED=True,
    NOTIFICATION_EMAIL_ENABLED=True,
    NOTIFICATION_EMAIL_TO="operator@example.com",
    NOTIFICATION_CRITICAL_REMINDER_SECONDS=3600,
    SMTP_HOST="fake.acceptance.invalid",
    SMTP_USERNAME="acceptance",
    SMTP_PASSWORD="not-a-real-secret",
    NOTIFICATION_FROM_EMAIL="alphapilot@example.com",
)


class FakeNotificationProvider:
    def __init__(self, results: list[NotificationSendResult] | None = None) -> None:
        self.results = results or [NotificationSendResult(delivered=True)]
        self.calls = 0

    def send(self, _notification: Notification) -> NotificationSendResult:
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


def assert_test_database() -> None:
    if os.getenv("ALPHAPILOT_SPRINT29_ACCEPTANCE") != "true":
        raise RuntimeError("Explicit Sprint 29 acceptance flag is required")
    if settings.TEST_DATABASE_URL is None or settings.DATABASE_URL != settings.TEST_DATABASE_URL:
        raise RuntimeError("Acceptance fixture requires DATABASE_URL to equal TEST_DATABASE_URL")


async def reset() -> None:
    assert_test_database()
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE notification_delivery_attempts, notifications, "
                "notification_preferences, operational_incident_events, "
                "operational_incidents CASCADE"
            )
        )
        await session.commit()


async def add_incident(
    session,
    *,
    incident_type: OperationalIncidentType,
    severity: OperationalSeverity,
    source: OperationalSourceDomain,
    identity: str,
    summary: str,
    evidence: dict[str, object],
) -> tuple[OperationalIncident, OperationalIncidentEvent]:
    key = f"{incident_type.value}:{source.value}:{identity}"
    incident = OperationalIncident(
        incident_type=incident_type.value,
        severity=severity.value,
        status=OperationalIncidentStatus.OPEN.value,
        source_domain=source.value,
        source_identity=identity,
        deduplication_key=key,
        active_deduplication_key=key,
        occurrence=1,
        opened_at=NOW,
        last_observed_at=NOW,
        summary=summary,
        evidence=evidence,
    )
    session.add(incident)
    await session.flush()
    event = OperationalIncidentEvent(
        incident_id=incident.id,
        event_type=OperationalEventType.OPENED.value,
        from_status=None,
        to_status=OperationalIncidentStatus.OPEN.value,
        source="SPRINT29_ACCEPTANCE",
        reason="Controlled browser acceptance",
        evidence=evidence,
        created_at=NOW,
    )
    session.add(event)
    await session.flush()
    return incident, event


async def seed() -> None:
    await reset()
    clock = [NOW]
    async with AsyncSessionLocal() as session:
        service = NotificationService(session, config=CONFIG, now_provider=lambda: clock[0])
        await service.update_preference(
            NotificationPreferenceUpdate(
                notifications_enabled=True,
                email_enabled=True,
                recipient="operator@example.com",
                warning_enabled=True,
                critical_enabled=True,
                recovery_enabled=True,
                daily_summary_enabled=True,
            )
        )
        critical, critical_event = await add_incident(
            session,
            incident_type=OperationalIncidentType.MANUAL_EXIT_ACTION_OVERDUE,
            severity=OperationalSeverity.CRITICAL,
            source=OperationalSourceDomain.EXTERNAL_EXECUTION,
            identity="hal-exit-overdue",
            summary="Manual exit action is overdue for HAL",
            evidence={
                "ticker": "HAL",
                "side": "SELL",
                "shares": 25,
                "expected_session": "2026-09-16",
                "reason": "SMA150_COMPLETED_CLOSE_EXIT",
            },
        )
        await service.plan_incident_transition(critical, critical_event, transition="OPENED")
        warning, warning_event = await add_incident(
            session,
            incident_type=OperationalIncidentType.FORWARD_ENGINE_STALE,
            severity=OperationalSeverity.WARNING,
            source=OperationalSourceDomain.FORWARD,
            identity="forward-1",
            summary="Forward processing is stale while completed sessions are pending",
            evidence={"pending_sessions": 1},
        )
        await service.plan_incident_transition(warning, warning_event, transition="OPENED")
        exit_required, exit_event = await add_incident(
            session,
            incident_type=OperationalIncidentType.MANUAL_EXIT_ACTION_REQUIRED,
            severity=OperationalSeverity.WARNING,
            source=OperationalSourceDomain.EXTERNAL_EXECUTION,
            identity="apa-exit",
            summary="Manual exit action is required for APA",
            evidence={"ticker": "APA", "side": "SELL", "shares": 10},
        )
        await service.plan_incident_transition(exit_required, exit_event, transition="OPENED")
        await add_incident(
            session,
            incident_type=OperationalIncidentType.EXTERNAL_BUY_ACTION_UPCOMING,
            severity=OperationalSeverity.INFO,
            source=OperationalSourceDomain.EXTERNAL_EXECUTION,
            identity="buy-upcoming",
            summary="Manual BUY action for IBM is upcoming",
            evidence={"ticker": "IBM", "side": "BUY", "shares": 5},
        )
        recovered, recovered_event = await add_incident(
            session,
            incident_type=OperationalIncidentType.BROKER_SYNC_FAILED,
            severity=OperationalSeverity.WARNING,
            source=OperationalSourceDomain.BROKER,
            identity="alpaca-paper",
            summary="Alpaca read-only synchronization most recently failed",
            evidence={"environment": "PAPER"},
        )
        await service.plan_incident_transition(recovered, recovered_event, transition="OPENED")
        critical_id = critical.id
        recovered_id = recovered.id
        await session.commit()
        await NotificationDeliveryWorker(
            session, FakeNotificationProvider(), config=CONFIG, now_provider=lambda: clock[0]
        ).run_pending()

        clock[0] += timedelta(hours=1)
        await service.plan_critical_reminders()
        await NotificationDeliveryWorker(
            session, FakeNotificationProvider(), config=CONFIG, now_provider=lambda: clock[0]
        ).run_pending()
        session.expunge_all()
        critical = await session.get(OperationalIncident, critical_id)
        recovered = await session.get(OperationalIncident, recovered_id)
        assert critical is not None and recovered is not None
        critical.status = OperationalIncidentStatus.ACKNOWLEDGED.value
        critical.acknowledged_at = clock[0]
        session.add(
            OperationalIncidentEvent(
                incident_id=critical_id,
                event_type=OperationalEventType.ACKNOWLEDGED.value,
                from_status=OperationalIncidentStatus.OPEN.value,
                to_status=OperationalIncidentStatus.ACKNOWLEDGED.value,
                source="USER",
                reason="Acceptance acknowledgement suppresses later reminders",
                evidence={},
                created_at=clock[0],
            )
        )

        recovered.status = OperationalIncidentStatus.RESOLVED.value
        recovered.active_deduplication_key = None
        recovered.resolved_at = clock[0]
        recovery_event = OperationalIncidentEvent(
            incident_id=recovered_id,
            event_type=OperationalEventType.RESOLVED.value,
            from_status=OperationalIncidentStatus.OPEN.value,
            to_status=OperationalIncidentStatus.RESOLVED.value,
            source="SPRINT29_ACCEPTANCE",
            reason="Broker sync restored",
            evidence=recovered.evidence,
            created_at=clock[0],
        )
        session.add(recovery_event)
        await session.flush()
        await service.plan_incident_transition(recovered, recovery_event, transition="RESOLVED")
        await session.commit()
        await NotificationDeliveryWorker(
            session, FakeNotificationProvider(), config=CONFIG, now_provider=lambda: clock[0]
        ).run_pending()

        summary = DailyOperationsSummarySchema(
            generated_at=clock[0],
            overall_health="DEGRADED",
            critical_count=1,
            warning_count=2,
            forward=ForwardOperationsSchema(
                status="ACTIVE",
                scheduler_status="SUCCEEDED",
                scheduler_running=True,
                cash=Decimal("50000"),
                equity=Decimal("101000"),
                open_positions=2,
                pending_sessions=0,
                latest_processed_session=date(2026, 9, 16),
                latest_completed_market_session=date(2026, 9, 16),
            ),
            expected_manual_buys=1,
            expected_manual_sells=2,
            overdue_actions=1,
            broker=BrokerOperationsSchema(
                enabled=True,
                configured=True,
                environment="PAPER",
                status="SUCCEEDED",
                last_success_at=clock[0],
                data_age_seconds=30,
                snapshot_authoritative=True,
            ),
            unmatched_broker_activity=0,
            ambiguous_matches=0,
            execution_conflicts=0,
            position_drift_count=0,
            latest_completed_market_session=date(2026, 9, 16),
            latest_forward_processed_session=date(2026, 9, 16),
        )
        await service.plan_daily_summary(summary)
        await NotificationDeliveryWorker(
            session, FakeNotificationProvider(), config=CONFIG, now_provider=lambda: clock[0]
        ).run_pending()

        transient = await service.create_test()
        transient_row = await session.get(Notification, transient.id)
        assert transient_row is not None
        flaky = FakeNotificationProvider(
            [
                NotificationSendResult(delivered=False),
                NotificationSendResult(delivered=True),
            ]
        )
        worker = NotificationDeliveryWorker(
            session, flaky, config=CONFIG, now_provider=lambda: clock[0]
        )
        await worker.run_pending()
        await session.refresh(transient_row)
        clock[0] = transient_row.next_attempt_at
        await worker.run_pending()

        failed = await service.create_test()
        failed_row = await session.get(Notification, failed.id)
        assert failed_row is not None
        await NotificationDeliveryWorker(
            session,
            FakeNotificationProvider([NotificationSendResult(delivered=False, permanent=True)]),
            config=CONFIG,
            now_provider=lambda: clock[0],
        ).run_pending()
        await session.refresh(failed_row)
        assert failed_row.status == "FAILED"


async def deliver() -> None:
    assert_test_database()
    async with AsyncSessionLocal() as session:
        await NotificationDeliveryWorker(
            session,
            FakeNotificationProvider(),
            config=CONFIG,
            now_provider=lambda: datetime.now(UTC),
        ).run_pending(limit=100)


async def audit_financial_domains() -> None:
    assert_test_database()
    tables = (
        "research_portfolios",
        "research_positions",
        "research_trade_events",
        "paper_validation_records",
        "forward_portfolios",
        "forward_cycles",
        "forward_orders",
        "forward_positions",
        "forward_trades",
        "forward_events",
        "forward_equity_points",
        "broker_sync_runs",
        "broker_account_snapshots",
        "broker_position_snapshots",
        "broker_order_observations",
        "broker_executions",
    )
    async with AsyncSessionLocal() as session:
        counts = {
            table: int(await session.scalar(text(f"SELECT count(*) FROM {table}")) or 0)
            for table in tables
        }
    if any(counts.values()):
        raise RuntimeError(f"Financial acceptance state changed: {counts}")
    print("Sprint 29 financial-domain acceptance audit passed: all protected counts are zero")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["reset", "seed", "deliver", "audit"])
    args = parser.parse_args()
    asyncio.run(
        {
            "reset": reset,
            "seed": seed,
            "deliver": deliver,
            "audit": audit_financial_domains,
        }[args.mode]()
    )


if __name__ == "__main__":
    main()
