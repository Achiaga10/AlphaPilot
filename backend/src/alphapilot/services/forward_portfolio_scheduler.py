from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class ForwardSchedulerRunStatus(StrEnum):
    NEVER_RUN = "NEVER_RUN"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    NO_PORTFOLIO = "NO_PORTFOLIO"
    NO_NEW_SESSION = "NO_NEW_SESSION"
    FAILED = "FAILED"


@dataclass(slots=True, frozen=True)
class ForwardSchedulerStatus:
    enabled: bool
    scheduler_running: bool = False
    interval_seconds: int = 3600
    last_run_started: datetime | None = None
    last_run_completed: datetime | None = None
    last_status: ForwardSchedulerRunStatus = ForwardSchedulerRunStatus.NEVER_RUN
    last_error: str | None = None


ForwardSchedulerJob = Callable[[], Awaitable[ForwardSchedulerRunStatus]]


class ForwardPortfolioScheduler:
    def __init__(
        self,
        *,
        enabled: bool,
        interval_seconds: int = 3600,
        job: ForwardSchedulerJob | None = None,
    ) -> None:
        if interval_seconds < 60:
            raise ValueError("Forward scheduler interval must be at least 60 seconds")
        self.status = ForwardSchedulerStatus(
            enabled=enabled,
            interval_seconds=interval_seconds,
        )
        self.job = job
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self.status.enabled and self.job is not None and self._task is None:
            self._stop.clear()
            self.status = replace(self.status, scheduler_running=True)
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self.status = replace(self.status, scheduler_running=False)

    async def run_once(self) -> ForwardSchedulerStatus:
        if self.job is None or self._lock.locked():
            return self.status
        async with self._lock:
            self.status = replace(
                self.status,
                last_run_started=datetime.now(UTC),
                last_status=ForwardSchedulerRunStatus.RUNNING,
                last_error=None,
            )
            try:
                outcome = await self.job()
                self.status = replace(
                    self.status,
                    last_run_completed=datetime.now(UTC),
                    last_status=outcome,
                )
            except Exception:
                self.status = replace(
                    self.status,
                    last_run_completed=datetime.now(UTC),
                    last_status=ForwardSchedulerRunStatus.FAILED,
                    last_error="Forward cycle failed. Review structured server logs.",
                )
            return self.status

    async def _loop(self) -> None:
        await self.run_once()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.status.interval_seconds)
            except TimeoutError:
                await self.run_once()
