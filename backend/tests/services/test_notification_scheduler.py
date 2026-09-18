from __future__ import annotations

import asyncio

import pytest

from alphapilot.services.notification_scheduler import (
    NotificationScheduler,
    NotificationSchedulerRunStatus,
)


@pytest.mark.asyncio
async def test_notification_scheduler_disabled_stays_stopped() -> None:
    scheduler = NotificationScheduler(enabled=False)
    scheduler.start()
    assert scheduler.status.scheduler_running is False
    assert scheduler.status.last_status == NotificationSchedulerRunStatus.NEVER_RUN
    await scheduler.stop()


@pytest.mark.asyncio
async def test_notification_scheduler_runs_immediately_and_contains_failure() -> None:
    called = asyncio.Event()

    async def succeeds() -> None:
        called.set()

    scheduler = NotificationScheduler(enabled=True, interval_seconds=10, job=succeeds)
    scheduler.start()
    await asyncio.wait_for(called.wait(), timeout=1)
    for _ in range(20):
        if scheduler.status.last_status == NotificationSchedulerRunStatus.SUCCEEDED:
            break
        await asyncio.sleep(0)
    assert scheduler.status.last_status == NotificationSchedulerRunStatus.SUCCEEDED
    await scheduler.stop()

    async def fails() -> None:
        raise RuntimeError("synthetic provider failure")

    failed = NotificationScheduler(enabled=True, interval_seconds=10, job=fails)
    result = await failed.run_once()
    assert result.last_status == NotificationSchedulerRunStatus.FAILED
    assert result.last_error == "Notification processing failed; review structured server logs."
