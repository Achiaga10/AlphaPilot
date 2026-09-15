from __future__ import annotations

import asyncio

import pytest

from alphapilot.services.broker_sync_scheduler import (
    BrokerSchedulerRunStatus,
    BrokerSyncScheduler,
)


@pytest.mark.asyncio
async def test_broker_scheduler_is_disabled_without_starting() -> None:
    scheduler = BrokerSyncScheduler(enabled=False)
    scheduler.start()
    assert scheduler.status.scheduler_running is False
    assert scheduler.status.last_status == BrokerSchedulerRunStatus.NEVER_RUN
    await scheduler.stop()


@pytest.mark.asyncio
async def test_broker_scheduler_runs_immediately_and_contains_failure() -> None:
    called = asyncio.Event()

    async def job() -> bool:
        called.set()
        return False

    scheduler = BrokerSyncScheduler(enabled=True, interval_seconds=60, job=job)
    scheduler.start()
    await asyncio.wait_for(called.wait(), timeout=1)
    for _ in range(20):
        if scheduler.status.last_status == BrokerSchedulerRunStatus.FAILED:
            break
        await asyncio.sleep(0)
    assert scheduler.status.scheduler_running is True
    assert scheduler.status.last_status == BrokerSchedulerRunStatus.FAILED
    await scheduler.stop()
    assert scheduler.status.scheduler_running is False
