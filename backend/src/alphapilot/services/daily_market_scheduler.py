from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


class DailySyncStatus(StrEnum):
    NEVER_RUN = "NEVER_RUN"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    NO_NEW_SESSION = "NO_NEW_SESSION"
    FAILED = "FAILED"


@dataclass(slots=True, frozen=True)
class DailySchedulerStatus:
    enabled: bool
    timezone: str = "America/New_York"
    scheduled_local_time: str = "16:30"
    last_run_started: datetime | None = None
    last_run_completed: datetime | None = None
    last_status: DailySyncStatus = DailySyncStatus.NEVER_RUN
    last_successful_completed_market_session: str | None = None
    last_error_summary: str | None = None


DailyJob = Callable[[], Awaitable[tuple[DailySyncStatus, str | None]]]


class DailyMarketSyncScheduler:
    def __init__(self, *, enabled: bool, job: DailyJob | None = None) -> None:
        self.status = DailySchedulerStatus(enabled=enabled)
        self.job = job
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self.status.enabled and self.job is not None and self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def run_once(self) -> DailySchedulerStatus:
        if self.job is None:
            return self.status
        if self._lock.locked():
            return self.status
        async with self._lock:
            self.status = replace(
                self.status,
                last_run_started=datetime.now(UTC),
                last_status=DailySyncStatus.RUNNING,
                last_error_summary=None,
            )
            try:
                outcome, session = await self.job()
                self.status = replace(
                    self.status,
                    last_run_completed=datetime.now(UTC),
                    last_status=outcome,
                    last_successful_completed_market_session=(
                        session
                        if outcome in {DailySyncStatus.SUCCEEDED, DailySyncStatus.NO_NEW_SESSION}
                        else self.status.last_successful_completed_market_session
                    ),
                )
            except Exception:
                self.status = replace(
                    self.status,
                    last_run_completed=datetime.now(UTC),
                    last_status=DailySyncStatus.FAILED,
                    last_error_summary=(
                        "Daily stored-data synchronization failed. Review server logs."
                    ),
                )
            return self.status

    async def _loop(self) -> None:
        while not self._stop.is_set():
            delay = self.seconds_until_next_run(datetime.now(UTC))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except TimeoutError:
                await self.run_once()

    @staticmethod
    def seconds_until_next_run(now: datetime) -> float:
        zone = ZoneInfo("America/New_York")
        local = now.astimezone(zone)
        candidate = datetime.combine(local.date(), time(16, 30), tzinfo=zone)
        while candidate <= local or candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return max((candidate.astimezone(UTC) - now.astimezone(UTC)).total_seconds(), 0)
