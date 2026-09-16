from __future__ import annotations

import asyncio

import pytest

from alphapilot.services.operations_scheduler import (
    OperationsMonitorScheduler,
    OperationsSchedulerRunStatus,
)


@pytest.mark.asyncio
async def test_operations_scheduler_is_disabled_without_starting() -> None:
    scheduler = OperationsMonitorScheduler(enabled=False)
    scheduler.start()
    assert scheduler.status.scheduler_running is False
    assert scheduler.status.last_status == OperationsSchedulerRunStatus.NEVER_RUN
    await scheduler.stop()


@pytest.mark.asyncio
async def test_operations_scheduler_runs_immediately() -> None:
    called = asyncio.Event()

    async def job() -> None:
        called.set()

    scheduler = OperationsMonitorScheduler(enabled=True, interval_seconds=60, job=job)
    scheduler.start()
    await asyncio.wait_for(called.wait(), timeout=1)
    for _ in range(20):
        if scheduler.status.last_status == OperationsSchedulerRunStatus.SUCCEEDED:
            break
        await asyncio.sleep(0)
    assert scheduler.status.last_status == OperationsSchedulerRunStatus.SUCCEEDED
    await scheduler.stop()


@pytest.mark.asyncio
async def test_operations_scheduler_contains_monitor_failure() -> None:
    async def job() -> None:
        raise RuntimeError("synthetic monitor failure")

    scheduler = OperationsMonitorScheduler(enabled=True, interval_seconds=60, job=job)
    result = await scheduler.run_once()
    assert result.last_status == OperationsSchedulerRunStatus.FAILED
    assert result.last_error == "Operations evaluation failed; review structured server logs."
