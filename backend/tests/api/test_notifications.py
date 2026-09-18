from __future__ import annotations

import pytest
from sqlalchemy import select

from alphapilot.api.routes.notifications import get_notification_service
from alphapilot.core.config import Settings
from alphapilot.database.models.notifications import Notification, NotificationStatus
from alphapilot.main import app
from alphapilot.services.notifications import NotificationService


def api_settings() -> Settings:
    return Settings(
        DEBUG=False,
        NOTIFICATIONS_ENABLED=True,
        NOTIFICATION_EMAIL_ENABLED=True,
        NOTIFICATION_EMAIL_TO="operator@example.com",
        SMTP_HOST="smtp.test",
        SMTP_USERNAME="operator",
        SMTP_PASSWORD="test-secret",
        NOTIFICATION_FROM_EMAIL="alphapilot@example.com",
    )


@pytest.mark.asyncio
async def test_notification_api_status_preferences_test_history_and_retry(
    client, db_session
) -> None:
    async def override_service() -> NotificationService:
        return NotificationService(db_session, config=api_settings(), worker_running=True)

    app.dependency_overrides[get_notification_service] = override_service
    try:
        defaults = await client.get("/api/v1/notifications/preferences")
        assert defaults.status_code == 200
        assert defaults.json()["notifications_enabled"] is False

        updated = await client.put(
            "/api/v1/notifications/preferences",
            json={
                "notifications_enabled": True,
                "email_enabled": True,
                "recipient": "operator@example.com",
                "warning_enabled": True,
                "critical_enabled": True,
                "recovery_enabled": True,
                "daily_summary_enabled": False,
            },
        )
        assert updated.status_code == 200

        status = await client.get("/api/v1/notifications/status")
        assert status.status_code == 200
        assert status.json() == {
            "enabled": True,
            "email_enabled": True,
            "configured": True,
            "worker_running": True,
            "queue_depth": 0,
            "pending_count": 0,
            "failed_count": 0,
            "last_delivery_at": None,
            "last_error": None,
        }

        created = await client.post("/api/v1/notifications/test", json={})
        assert created.status_code == 201
        assert created.json()["kind"] == "TEST"
        assert created.json()["status"] == "PENDING"
        notification_id = created.json()["id"]

        listed = await client.get("/api/v1/notifications")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [notification_id]
        detail = await client.get(f"/api/v1/notifications/{notification_id}")
        assert detail.status_code == 200
        assert detail.json()["attempts"] == []

        retry_pending = await client.post(f"/api/v1/notifications/{notification_id}/retry")
        assert retry_pending.status_code == 409
        row = await db_session.scalar(
            select(Notification).where(Notification.id == notification_id)
        )
        assert row is not None
        row.status = NotificationStatus.FAILED.value
        await db_session.commit()
        retried = await client.post(f"/api/v1/notifications/{notification_id}/retry")
        assert retried.status_code == 200
        assert retried.json()["status"] == "RETRY_PENDING"
    finally:
        app.dependency_overrides.pop(get_notification_service, None)


@pytest.mark.asyncio
async def test_notification_api_validation_disabled_missing_and_no_delete(client) -> None:
    invalid = await client.put(
        "/api/v1/notifications/preferences",
        json={
            "notifications_enabled": True,
            "email_enabled": True,
            "recipient": "not-an-email",
            "warning_enabled": True,
            "critical_enabled": True,
            "recovery_enabled": True,
            "daily_summary_enabled": False,
        },
    )
    assert invalid.status_code == 422
    disabled = await client.post("/api/v1/notifications/test", json={})
    assert disabled.status_code == 409
    missing = await client.get("/api/v1/notifications/10000000-0000-4000-8000-000000000099")
    assert missing.status_code == 404
    deleted = await client.delete("/api/v1/notifications/10000000-0000-4000-8000-000000000099")
    assert deleted.status_code == 405
