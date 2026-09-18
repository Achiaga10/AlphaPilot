"""Deterministic notification policy, durable outbox, and delivery worker."""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.core.config import Settings, settings
from alphapilot.database.models.notifications import (
    Notification,
    NotificationAttemptResult,
    NotificationChannel,
    NotificationDeliveryAttempt,
    NotificationFailureCategory,
    NotificationKind,
    NotificationPreference,
    NotificationPriority,
    NotificationStatus,
)
from alphapilot.database.models.operations import (
    OperationalIncident,
    OperationalIncidentEvent,
    OperationalIncidentStatus,
    OperationalIncidentType,
    OperationalSeverity,
    OperationalSourceDomain,
)
from alphapilot.notifications.email import NotificationProvider, NotificationSendResult
from alphapilot.schemas.notifications import (
    NotificationAttemptSchema,
    NotificationPreferenceSchema,
    NotificationPreferenceUpdate,
    NotificationSchema,
    NotificationStatusSchema,
)
from alphapilot.schemas.operations import DailyOperationsSummarySchema

logger = logging.getLogger(__name__)

ACTIONABLE_WARNING_TYPES = frozenset(
    {
        OperationalIncidentType.FORWARD_ENGINE_FAILED.value,
        OperationalIncidentType.FORWARD_ENGINE_STALE.value,
        OperationalIncidentType.FORWARD_CYCLE_FAILED.value,
        OperationalIncidentType.MARKET_DATA_STALE.value,
        OperationalIncidentType.MARKET_DATA_MISSING.value,
        OperationalIncidentType.MARKET_SYNC_FAILED.value,
        OperationalIncidentType.BROKER_SYNC_FAILED.value,
        OperationalIncidentType.BROKER_SYNC_STALE.value,
        OperationalIncidentType.BROKER_SYNC_MISCONFIGURED.value,
        OperationalIncidentType.EXTERNAL_ACTION_OVERDUE.value,
        OperationalIncidentType.MANUAL_EXIT_ACTION_REQUIRED.value,
        OperationalIncidentType.PARTIAL_EXTERNAL_EXECUTION.value,
        OperationalIncidentType.BROKER_MATCH_AMBIGUOUS.value,
        OperationalIncidentType.BROKER_EXECUTION_CONFLICT.value,
        OperationalIncidentType.POSITION_QUANTITY_DRIFT.value,
    }
)
NOTIFICATION_INCIDENT_TYPES = frozenset(
    {
        "NOTIFICATION_DELIVERY_FAILED",
        "NOTIFICATION_QUEUE_STALE",
        "NOTIFICATION_MISCONFIGURED",
    }
)
RETRY_DELAYS_SECONDS = (60, 300, 900, 1800)


class NotificationNotFoundError(ValueError):
    pass


class NotificationConflictError(ValueError):
    pass


class NotificationConfigurationError(ValueError):
    pass


def _valid_email(value: str | None) -> bool:
    if not value or value.count("@") != 1:
        return False
    local, domain = value.rsplit("@", 1)
    return bool(local and "." in domain and not domain.startswith(".") and not domain.endswith("."))


def notification_system_configured(config: Settings) -> bool:
    auth_complete = bool(config.SMTP_USERNAME) == bool(config.SMTP_PASSWORD)
    return bool(
        config.SMTP_HOST
        and config.SMTP_PORT > 0
        and config.NOTIFICATION_FROM_EMAIL
        and auth_complete
    )


class NotificationService:
    """Own notification policy and outbox writes, never provider I/O."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        config: Settings = settings,
        now_provider: Callable[[], datetime] | None = None,
        worker_running: bool = False,
    ) -> None:
        self.session = session
        self.config = config
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.worker_running = worker_running

    async def preference(self) -> NotificationPreferenceSchema:
        row = await self._preference_row()
        if row is None:
            return NotificationPreferenceSchema()
        return NotificationPreferenceSchema(
            notifications_enabled=row.notifications_enabled,
            email_enabled=row.email_enabled,
            recipient=row.recipient,
            warning_enabled=row.warning_enabled,
            critical_enabled=row.critical_enabled,
            recovery_enabled=row.recovery_enabled,
            daily_summary_enabled=row.daily_summary_enabled,
        )

    async def update_preference(
        self, request: NotificationPreferenceUpdate
    ) -> NotificationPreferenceSchema:
        row = await self._preference_row(for_update=True)
        if row is None:
            row = NotificationPreference(profile_key="DEFAULT_OPERATOR")
            self.session.add(row)
        for name, value in request.model_dump().items():
            setattr(row, name, value)
        await self.session.commit()
        return await self.preference()

    async def status(self) -> NotificationStatusSchema:
        preference = await self.preference()
        pending_states = [
            NotificationStatus.PENDING.value,
            NotificationStatus.RETRY_PENDING.value,
            NotificationStatus.DELIVERING.value,
        ]
        pending = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.status.in_(pending_states))
            )
            or 0
        )
        failed = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.status == NotificationStatus.FAILED.value)
            )
            or 0
        )
        last_delivery = await self.session.scalar(select(func.max(Notification.sent_at)))
        last_failed = await self.session.scalar(
            select(Notification)
            .where(Notification.failure_category.is_not(None))
            .order_by(Notification.last_attempt_at.desc())
            .limit(1)
        )
        enabled = self.config.NOTIFICATIONS_ENABLED and preference.notifications_enabled
        email_enabled = (
            enabled and self.config.NOTIFICATION_EMAIL_ENABLED and preference.email_enabled
        )
        return NotificationStatusSchema(
            enabled=enabled,
            email_enabled=email_enabled,
            configured=notification_system_configured(self.config),
            worker_running=self.worker_running,
            queue_depth=pending,
            pending_count=pending,
            failed_count=failed,
            last_delivery_at=last_delivery,
            last_error=(
                NotificationFailureCategory(last_failed.failure_category)
                if last_failed is not None and last_failed.failure_category
                else None
            ),
        )

    async def list_notifications(self, *, limit: int = 100) -> list[NotificationSchema]:
        rows = list(
            (
                await self.session.execute(
                    select(Notification).order_by(Notification.created_at.desc()).limit(limit)
                )
            ).scalars()
        )
        return [await self._schema(row, include_attempts=False) for row in rows]

    async def notification(self, notification_id: UUID) -> NotificationSchema:
        row = await self.session.get(Notification, notification_id)
        if row is None:
            raise NotificationNotFoundError("Notification not found")
        return await self._schema(row, include_attempts=True)

    async def retry(self, notification_id: UUID) -> NotificationSchema:
        row = await self.session.get(Notification, notification_id, with_for_update=True)
        if row is None:
            raise NotificationNotFoundError("Notification not found")
        if row.status != NotificationStatus.FAILED.value:
            raise NotificationConflictError("Only failed notifications can be retried")
        row.status = NotificationStatus.RETRY_PENDING.value
        row.next_attempt_at = self.now_provider()
        row.failure_category = None
        row.lease_token = None
        row.lease_expires_at = None
        await self.session.commit()
        return await self.notification(notification_id)

    async def create_test(self, recipient: str | None = None) -> NotificationSchema:
        preference = await self.preference()
        target = recipient or preference.recipient or self.config.NOTIFICATION_EMAIL_TO
        if not self._delivery_enabled(preference) or not notification_system_configured(
            self.config
        ):
            raise NotificationConfigurationError(
                "Notifications, email delivery, preferences, and SMTP must be enabled/configured"
            )
        if not _valid_email(target):
            raise NotificationConfigurationError("A valid notification recipient is required")
        now = self.now_provider()
        token = uuid4()
        row = Notification(
            channel=NotificationChannel.EMAIL.value,
            status=NotificationStatus.PENDING.value,
            kind=NotificationKind.TEST.value,
            priority=NotificationPriority.TEST.value,
            transition="TEST",
            generation=1,
            recipient=target,
            subject="[AlphaPilot][TEST] Operational notification",
            body_text=(
                "TEST AlphaPilot operational notification\n\n"
                "This message verifies the configured email delivery path.\n"
                "It has no incident, strategy, portfolio, or trading authority."
            ),
            body_html=None,
            deduplication_key=f"test:{token}:EMAIL",
            scheduled_at=now,
            next_attempt_at=now,
        )
        self.session.add(row)
        await self.session.commit()
        return await self.notification(row.id)

    async def plan_incident_transition(
        self,
        incident: OperationalIncident,
        event: OperationalIncidentEvent,
        *,
        transition: str,
        generation: int | None = 1,
    ) -> Notification | None:
        if (
            incident.source_domain == OperationalSourceDomain.NOTIFICATION.value
            or incident.incident_type in NOTIFICATION_INCIDENT_TYPES
        ):
            return None
        preference = await self.preference()
        if not self._delivery_enabled(preference):
            return None
        recipient = preference.recipient or self.config.NOTIFICATION_EMAIL_TO
        if not _valid_email(recipient):
            return None

        if transition == "RESOLVED":
            if not preference.recovery_enabled:
                return None
            delivered = await self.session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.incident_id == incident.id,
                    Notification.status == NotificationStatus.DELIVERED.value,
                    Notification.kind.in_(
                        [
                            NotificationKind.INCIDENT.value,
                            NotificationKind.REMINDER.value,
                        ]
                    ),
                )
            )
            if not delivered:
                return None
            kind = NotificationKind.RECOVERY
            priority = NotificationPriority.RECOVERED
        elif incident.severity == OperationalSeverity.CRITICAL.value:
            if not preference.critical_enabled:
                return None
            kind = NotificationKind.INCIDENT
            priority = NotificationPriority.CRITICAL
        elif (
            incident.severity == OperationalSeverity.WARNING.value
            and incident.incident_type in ACTIONABLE_WARNING_TYPES
        ):
            if not preference.warning_enabled:
                return None
            kind = NotificationKind.INCIDENT
            priority = NotificationPriority.WARNING
        else:
            return None

        if generation is None:
            generation = (
                int(
                    await self.session.scalar(
                        select(func.max(Notification.generation)).where(
                            Notification.incident_id == incident.id,
                            Notification.transition == transition,
                        )
                    )
                    or 0
                )
                + 1
            )
        key = f"incident:{incident.id}:{transition}:{generation}:EMAIL"
        return await self._create_if_absent(
            incident=incident,
            event=event,
            recipient=recipient,
            kind=kind,
            priority=priority,
            transition=transition,
            generation=generation,
            deduplication_key=key,
        )

    async def plan_critical_reminders(self) -> int:
        preference = await self.preference()
        if not self._delivery_enabled(preference) or not preference.critical_enabled:
            return 0
        recipient = preference.recipient or self.config.NOTIFICATION_EMAIL_TO
        if not _valid_email(recipient):
            return 0
        now = self.now_provider()
        incidents = list(
            (
                await self.session.execute(
                    select(OperationalIncident).where(
                        OperationalIncident.status == OperationalIncidentStatus.OPEN.value,
                        OperationalIncident.severity == OperationalSeverity.CRITICAL.value,
                        OperationalIncident.source_domain
                        != OperationalSourceDomain.NOTIFICATION.value,
                    )
                )
            ).scalars()
        )
        created = 0
        for incident in incidents:
            delivered_rows = list(
                (
                    await self.session.execute(
                        select(Notification)
                        .where(
                            Notification.incident_id == incident.id,
                            Notification.status == NotificationStatus.DELIVERED.value,
                        )
                        .order_by(Notification.sent_at.desc())
                    )
                ).scalars()
            )
            if not delivered_rows or delivered_rows[0].sent_at is None:
                continue
            if (now - delivered_rows[0].sent_at).total_seconds() < (
                self.config.NOTIFICATION_CRITICAL_REMINDER_SECONDS
            ):
                continue
            generation = (
                sum(row.kind == NotificationKind.REMINDER.value for row in delivered_rows) + 1
            )
            key = f"incident:{incident.id}:REMINDER:{generation}:EMAIL"
            if await self.session.scalar(
                select(Notification.id).where(Notification.deduplication_key == key)
            ):
                continue
            subject, body = self._render_incident(
                incident, NotificationPriority.CRITICAL, reminder=True
            )
            self.session.add(
                Notification(
                    incident_id=incident.id,
                    channel=NotificationChannel.EMAIL.value,
                    status=NotificationStatus.PENDING.value,
                    kind=NotificationKind.REMINDER.value,
                    priority=NotificationPriority.CRITICAL.value,
                    transition="REMINDER",
                    generation=generation,
                    recipient=recipient,
                    subject=subject,
                    body_text=body,
                    body_html=self._html(body),
                    deduplication_key=key,
                    scheduled_at=now,
                    next_attempt_at=now,
                )
            )
            created += 1
        if created:
            await self.session.commit()
        return created

    async def plan_active_incidents(self) -> int:
        """Backfill newly enabled delivery for active eligible incidents without polling spam."""
        incidents = list(
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
        created = 0
        for incident in incidents:
            event = await self.session.scalar(
                select(OperationalIncidentEvent)
                .where(
                    OperationalIncidentEvent.incident_id == incident.id,
                    OperationalIncidentEvent.event_type == "OPENED",
                )
                .order_by(OperationalIncidentEvent.created_at)
                .limit(1)
            )
            if event is not None and await self.plan_incident_transition(
                incident, event, transition="OPENED"
            ):
                created += 1
        if created:
            await self.session.commit()
        return created

    async def cancel_pending_for_incident(self, incident_id: UUID, *, reminders_only: bool) -> int:
        statement = select(Notification).where(
            Notification.incident_id == incident_id,
            Notification.status.in_(
                [
                    NotificationStatus.PENDING.value,
                    NotificationStatus.RETRY_PENDING.value,
                ]
            ),
        )
        if reminders_only:
            statement = statement.where(Notification.kind == NotificationKind.REMINDER.value)
        rows = list((await self.session.execute(statement.with_for_update())).scalars())
        for row in rows:
            row.status = NotificationStatus.CANCELLED.value
            row.lease_token = None
            row.lease_expires_at = None
        return len(rows)

    async def plan_daily_summary(
        self, summary: DailyOperationsSummarySchema
    ) -> Notification | None:
        preference = await self.preference()
        if not self._delivery_enabled(preference) or not preference.daily_summary_enabled:
            return None
        recipient = preference.recipient or self.config.NOTIFICATION_EMAIL_TO
        session = summary.latest_completed_market_session
        if not _valid_email(recipient) or session is None:
            return None
        recipient_hash = hashlib.sha256(recipient.lower().encode()).hexdigest()[:16]
        key = f"daily:{session}:EMAIL:{recipient_hash}"
        now = self.now_provider()
        body = self._render_summary(summary)
        row = Notification(
            channel=NotificationChannel.EMAIL.value,
            status=NotificationStatus.PENDING.value,
            kind=NotificationKind.DAILY_SUMMARY.value,
            priority=NotificationPriority.SUMMARY.value,
            transition="DAILY_SUMMARY",
            generation=1,
            recipient=recipient,
            subject=f"[AlphaPilot][SUMMARY] Operations — {session}",
            body_text=body,
            body_html=self._html(body),
            deduplication_key=key,
            trading_session=session,
            scheduled_at=now,
            next_attempt_at=now,
        )
        if await self.session.scalar(
            select(Notification.id).where(Notification.deduplication_key == key)
        ):
            return None
        self.session.add(row)
        await self.session.commit()
        return row

    async def incident_delivery_state(self, incident: OperationalIncident) -> str:
        latest = await self.session.scalar(
            select(Notification)
            .where(Notification.incident_id == incident.id)
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        if latest is not None:
            if latest.status == NotificationStatus.DELIVERED.value:
                return "DELIVERED"
            if latest.status == NotificationStatus.FAILED.value:
                return "FAILED"
            if latest.status in {
                NotificationStatus.PENDING.value,
                NotificationStatus.DELIVERING.value,
                NotificationStatus.RETRY_PENDING.value,
            }:
                return "PENDING"
        if (
            incident.source_domain == OperationalSourceDomain.NOTIFICATION.value
            or incident.severity == OperationalSeverity.INFO.value
            or (
                incident.severity == OperationalSeverity.WARNING.value
                and incident.incident_type not in ACTIONABLE_WARNING_TYPES
            )
        ):
            return "NOT_ELIGIBLE"
        return "SUPPRESSED_BY_PREFERENCE"

    async def _preference_row(self, *, for_update: bool = False) -> NotificationPreference | None:
        statement = select(NotificationPreference).where(
            NotificationPreference.profile_key == "DEFAULT_OPERATOR"
        )
        if for_update:
            statement = statement.with_for_update()
        row: NotificationPreference | None = await self.session.scalar(statement)
        return row

    def _delivery_enabled(self, preference: NotificationPreferenceSchema) -> bool:
        return bool(
            self.config.NOTIFICATIONS_ENABLED
            and self.config.NOTIFICATION_EMAIL_ENABLED
            and preference.notifications_enabled
            and preference.email_enabled
            and notification_system_configured(self.config)
        )

    async def _create_if_absent(
        self,
        *,
        incident: OperationalIncident,
        event: OperationalIncidentEvent,
        recipient: str,
        kind: NotificationKind,
        priority: NotificationPriority,
        transition: str,
        generation: int,
        deduplication_key: str,
    ) -> Notification | None:
        if await self.session.scalar(
            select(Notification.id).where(Notification.deduplication_key == deduplication_key)
        ):
            return None
        now = self.now_provider()
        subject, body = self._render_incident(
            incident, priority, recovery=kind == NotificationKind.RECOVERY
        )
        row = Notification(
            incident_id=incident.id,
            incident_event_id=event.id,
            channel=NotificationChannel.EMAIL.value,
            status=NotificationStatus.PENDING.value,
            kind=kind.value,
            priority=priority.value,
            transition=transition,
            generation=generation,
            recipient=recipient,
            subject=subject,
            body_text=body,
            body_html=self._html(body),
            deduplication_key=deduplication_key,
            scheduled_at=now,
            next_attempt_at=now,
        )
        self.session.add(row)
        return row

    def _render_incident(
        self,
        incident: OperationalIncident,
        priority: NotificationPriority,
        *,
        reminder: bool = False,
        recovery: bool = False,
    ) -> tuple[str, str]:
        label = incident.summary.rstrip(".")
        if incident.incident_type == OperationalIncidentType.MANUAL_EXIT_ACTION_OVERDUE.value:
            ticker = incident.evidence.get("ticker", "unknown ticker")
            label = f"Manual exit overdue — {ticker}"
        elif incident.incident_type == OperationalIncidentType.FORWARD_ENGINE_STALE.value:
            label = "Forward engine stale"
        elif recovery and incident.incident_type.startswith("BROKER_SYNC_"):
            label = "Broker sync restored"
        marker = "RECOVERED" if recovery else priority.value
        if reminder:
            label = f"Reminder — {label}"
        broker_related = incident.source_domain in {
            OperationalSourceDomain.BROKER.value,
            OperationalSourceDomain.RECONCILIATION.value,
            OperationalSourceDomain.POSITION.value,
        }
        environment = str(incident.evidence.get("environment", self.config.ALPACA_ENVIRONMENT))
        live_prefix = "[LIVE]" if broker_related and environment == "LIVE" else ""
        subject = f"[AlphaPilot][{marker}]{live_prefix} {label}"
        lines = [
            "AlphaPilot operational notification",
            f"Environment: {environment if broker_related else 'APPLICATION'}",
            f"Severity: {incident.severity}",
            f"Incident: {incident.incident_type}",
            f"Status: {incident.status}",
            f"Summary: {incident.summary}",
            f"Opened at (UTC): {incident.opened_at.isoformat()}",
            f"Last observed (UTC): {incident.last_observed_at.isoformat()}",
        ]
        if broker_related and environment == "LIVE":
            lines.insert(1, "LIVE ACCOUNT OBSERVATION — read-only broker evidence")
        facts = incident.evidence
        for key, title in (
            ("ticker", "Ticker"),
            ("side", "Side"),
            ("shares", "Shares"),
            ("expected_session", "Execution session"),
            ("reason", "Reason"),
        ):
            value = facts.get(key)
            if value is not None:
                lines.append(f"{title}: {value}")
        if incident.incident_type in {
            OperationalIncidentType.MANUAL_EXIT_ACTION_REQUIRED.value,
            OperationalIncidentType.MANUAL_EXIT_ACTION_OVERDUE.value,
        }:
            lines.extend(
                [
                    "Manual broker SELL action required.",
                    "AlphaPilot has not submitted, cancelled, or executed a broker order.",
                ]
            )
        elif facts.get("side") == "BUY":
            lines.append("Manual broker BUY action expected; no BUY was submitted.")
        lines.append("This notification is observational and has zero trading authority.")
        return subject, "\n".join(lines)

    @staticmethod
    def _render_summary(summary: DailyOperationsSummarySchema) -> str:
        return "\n".join(
            [
                "AlphaPilot daily Operations summary",
                f"Completed trading session: {summary.latest_completed_market_session}",
                f"Overall health: {summary.overall_health.value}",
                f"Critical / warning: {summary.critical_count} / {summary.warning_count}",
                f"Forward equity: {summary.forward.equity}",
                f"Open positions: {summary.forward.open_positions}",
                f"Manual BUY / SELL actions: {summary.expected_manual_buys} / "
                f"{summary.expected_manual_sells}",
                f"Overdue actions: {summary.overdue_actions}",
                f"Broker sync: {summary.broker.environment} {summary.broker.status}",
                f"Reconciliation conflicts: {summary.execution_conflicts}",
                f"Position drift: {summary.position_drift_count}",
                "This summary is observational and has zero trading authority.",
            ]
        )

    @staticmethod
    def _html(body: str) -> str:
        return f"<pre>{html.escape(body)}</pre>"

    async def _schema(self, row: Notification, *, include_attempts: bool) -> NotificationSchema:
        attempts: list[NotificationAttemptSchema] = []
        if include_attempts:
            attempt_rows = list(
                (
                    await self.session.execute(
                        select(NotificationDeliveryAttempt)
                        .where(NotificationDeliveryAttempt.notification_id == row.id)
                        .order_by(NotificationDeliveryAttempt.attempt_number)
                    )
                ).scalars()
            )
            attempts = [NotificationAttemptSchema.model_validate(item) for item in attempt_rows]
        return NotificationSchema.model_validate(row).model_copy(update={"attempts": attempts})


class NotificationDeliveryWorker:
    """Lease and deliver outbox rows independently of Operations transactions."""

    def __init__(
        self,
        session: AsyncSession,
        provider: NotificationProvider,
        *,
        config: Settings = settings,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.config = config
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    async def run_pending(self, *, limit: int = 20) -> int:
        delivered = 0
        for _ in range(limit):
            claimed = await self._claim_one()
            if claimed is None:
                break
            notification, lease_token, started_at = claimed
            monotonic_started = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self.provider.send, notification),
                    timeout=self.config.SMTP_TIMEOUT_SECONDS + 2,
                )
            except TimeoutError:
                result = NotificationSendResult(
                    delivered=False,
                    failure_category=NotificationFailureCategory.TIMEOUT,
                )
            duration_ms = max(0, round((time.monotonic() - monotonic_started) * 1000))
            if await self._finish(notification.id, lease_token, started_at, duration_ms, result):
                delivered += 1
        return delivered

    async def _claim_one(self) -> tuple[Notification, UUID, datetime] | None:
        now = self.now_provider()
        eligible = or_(
            Notification.status.in_(
                [NotificationStatus.PENDING.value, NotificationStatus.RETRY_PENDING.value]
            ),
            (
                (Notification.status == NotificationStatus.DELIVERING.value)
                & (Notification.lease_expires_at <= now)
            ),
        )
        row = await self.session.scalar(
            select(Notification)
            .where(eligible, Notification.next_attempt_at <= now)
            .order_by(Notification.next_attempt_at, Notification.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            await self.session.rollback()
            return None
        token = uuid4()
        row.status = NotificationStatus.DELIVERING.value
        row.attempt_count += 1
        row.last_attempt_at = now
        row.lease_token = token
        row.lease_expires_at = now + timedelta(
            seconds=self.config.NOTIFICATION_DELIVERY_LEASE_SECONDS
        )
        await self.session.commit()
        return row, token, now

    async def _finish(
        self,
        notification_id: UUID,
        lease_token: UUID,
        started_at: datetime,
        duration_ms: int,
        result: NotificationSendResult,
    ) -> bool:
        row = await self.session.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.lease_token == lease_token,
                Notification.status == NotificationStatus.DELIVERING.value,
            )
            .with_for_update()
        )
        if row is None:
            await self.session.rollback()
            return False
        now = self.now_provider()
        category = result.failure_category.value if result.failure_category else None
        if result.delivered:
            row.status = NotificationStatus.DELIVERED.value
            row.sent_at = now
            row.failure_category = None
            row.provider_message_reference = result.provider_message_reference
            attempt_result = NotificationAttemptResult.DELIVERED
        else:
            permanent = (
                result.permanent or row.attempt_count >= self.config.NOTIFICATION_MAX_ATTEMPTS
            )
            row.status = (
                NotificationStatus.FAILED.value
                if permanent
                else NotificationStatus.RETRY_PENDING.value
            )
            row.failure_category = category or NotificationFailureCategory.PROVIDER_ERROR.value
            if not permanent:
                delay = RETRY_DELAYS_SECONDS[
                    min(row.attempt_count - 1, len(RETRY_DELAYS_SECONDS) - 1)
                ]
                row.next_attempt_at = now + timedelta(seconds=delay)
            attempt_result = (
                NotificationAttemptResult.PERMANENT_FAILURE
                if permanent
                else NotificationAttemptResult.TRANSIENT_FAILURE
            )
        row.lease_token = None
        row.lease_expires_at = None
        self.session.add(
            NotificationDeliveryAttempt(
                notification_id=row.id,
                attempt_number=row.attempt_count,
                started_at=started_at,
                completed_at=now,
                result=attempt_result.value,
                failure_category=category,
                provider_message_reference=result.provider_message_reference,
                duration_ms=duration_ms,
            )
        )
        await self.session.commit()
        logger.info(
            "notification_delivery notification_id=%s incident_id=%s channel=%s "
            "attempt=%s result=%s duration_ms=%s",
            row.id,
            row.incident_id,
            row.channel,
            row.attempt_count,
            attempt_result.value,
            duration_ms,
        )
        return result.delivered
