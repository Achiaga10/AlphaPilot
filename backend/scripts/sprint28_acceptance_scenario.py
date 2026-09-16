"""Create deterministic Sprint 28 browser scenarios in TEST_DATABASE_URL only."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta

os.environ["DEBUG"] = "false"

from alphapilot.core.config import Settings, settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["degraded", "recovered"])
    return parser.parse_args()


async def run(scenario: str) -> None:
    if settings.TEST_DATABASE_URL is None or settings.TEST_DATABASE_URL == settings.DATABASE_URL:
        raise RuntimeError("Acceptance scenarios require an isolated TEST_DATABASE_URL")
    settings.DATABASE_URL = settings.TEST_DATABASE_URL

    from alphapilot.database.models.broker_sync import BrokerSyncRun, BrokerSyncRunStatus
    from alphapilot.database.session import AsyncSessionLocal
    from alphapilot.services.operations_monitor import OperationsMonitor

    now = datetime.now(UTC)
    environment = "LIVE" if scenario == "degraded" else "PAPER"
    configured = Settings(
        DEBUG=False,
        DATABASE_URL=settings.TEST_DATABASE_URL,
        TEST_DATABASE_URL=settings.TEST_DATABASE_URL,
        ALPACA_SYNC_ENABLED=scenario == "degraded",
        ALPACA_API_KEY="",
        ALPACA_SECRET_KEY="",
        ALPACA_ENVIRONMENT="PAPER",
    )
    async with AsyncSessionLocal() as session:
        session.add(
            BrokerSyncRun(
                provider="ALPACA",
                environment=environment,
                status=BrokerSyncRunStatus.SUCCEEDED.value,
                started_at=now,
                completed_at=now,
                requested_after=now - timedelta(days=1),
            )
        )
        await session.commit()
        result = await OperationsMonitor(
            session,
            config=configured,
            now_provider=lambda: now,
            monitor_running=True,
        ).evaluate()
        print(result.overall_health.value)


def main() -> None:
    args = parse_args()
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.SelectorEventLoop()
    try:
        loop.run_until_complete(run(args.scenario))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
