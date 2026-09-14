from __future__ import annotations

import asyncio

import pytest

from alphapilot.services.forward_portfolio_scheduler import (
    ForwardPortfolioScheduler,
    ForwardSchedulerRunStatus,
)


@pytest.mark.asyncio
async def test_scheduler_runs_immediately_and_reports_status() -> None:
    called = asyncio.Event()

    async def job() -> ForwardSchedulerRunStatus:
        called.set()
        return ForwardSchedulerRunStatus.NO_NEW_SESSION

    scheduler = ForwardPortfolioScheduler(enabled=True, interval_seconds=60, job=job)
    scheduler.start()
    await asyncio.wait_for(called.wait(), timeout=1)
    assert scheduler.status.scheduler_running
    assert scheduler.status.last_status is ForwardSchedulerRunStatus.NO_NEW_SESSION
    assert scheduler.status.last_run_started is not None
    assert scheduler.status.last_run_completed is not None
    await scheduler.stop()
    assert not scheduler.status.scheduler_running


@pytest.mark.asyncio
async def test_scheduler_failure_is_contained_and_visible() -> None:
    async def job() -> ForwardSchedulerRunStatus:
        raise RuntimeError("provider secret must not leak")

    scheduler = ForwardPortfolioScheduler(enabled=True, interval_seconds=60, job=job)
    status = await scheduler.run_once()
    assert status.last_status is ForwardSchedulerRunStatus.FAILED
    assert status.last_error == "Forward cycle failed. Review structured server logs."
    assert "secret" not in status.last_error
