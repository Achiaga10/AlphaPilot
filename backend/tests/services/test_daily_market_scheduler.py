from datetime import UTC, datetime

import pytest

from alphapilot.services.daily_market_scheduler import (
    DailyMarketSyncScheduler,
    DailySyncStatus,
)


def test_scheduler_uses_1630_new_york_and_skips_weekends() -> None:
    friday_after_run = datetime(2026, 8, 28, 21, 0, tzinfo=UTC)
    seconds = DailyMarketSyncScheduler.seconds_until_next_run(friday_after_run)
    monday_run = friday_after_run.timestamp() + seconds
    assert datetime.fromtimestamp(monday_run, UTC).weekday() == 0
    assert seconds > 2 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_duplicate_run_is_serialized_and_no_new_session_is_explicit() -> None:
    calls = 0

    async def job() -> tuple[DailySyncStatus, str | None]:
        nonlocal calls
        calls += 1
        return DailySyncStatus.NO_NEW_SESSION, "2026-08-27"

    scheduler = DailyMarketSyncScheduler(enabled=True, job=job)
    status = await scheduler.run_once()
    assert calls == 1
    assert status.last_status == DailySyncStatus.NO_NEW_SESSION
    assert status.last_successful_completed_market_session == "2026-08-27"
