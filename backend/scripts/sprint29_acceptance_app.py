"""Controlled Sprint 29 browser-acceptance application wiring."""

from __future__ import annotations

import os
from typing import Annotated

os.environ["DEBUG"] = "false"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:5180"
os.environ["DAILY_MARKET_SYNC_ENABLED"] = "false"
os.environ["FORWARD_PORTFOLIO_SCHEDULER_ENABLED"] = "false"
os.environ["ALPACA_SYNC_ENABLED"] = "false"
os.environ["OPERATIONS_MONITOR_ENABLED"] = "false"
os.environ["NOTIFICATIONS_ENABLED"] = "false"

from fastapi import Depends  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from alphapilot.api.routes.notifications import get_notification_service  # noqa: E402
from alphapilot.core.config import Settings  # noqa: E402
from alphapilot.database.session import get_db  # noqa: E402
from alphapilot.main import app  # noqa: E402
from alphapilot.services.notifications import NotificationService  # noqa: E402

acceptance_config = Settings(
    DEBUG=False,
    NOTIFICATIONS_ENABLED=True,
    NOTIFICATION_EMAIL_ENABLED=True,
    NOTIFICATION_EMAIL_TO="operator@example.com",
    SMTP_HOST="fake.acceptance.invalid",
    SMTP_USERNAME="acceptance",
    SMTP_PASSWORD="not-a-real-secret",
    NOTIFICATION_FROM_EMAIL="alphapilot@example.com",
)


async def acceptance_notification_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationService:
    return NotificationService(
        session,
        config=acceptance_config,
        worker_running=True,
    )


app.dependency_overrides[get_notification_service] = acceptance_notification_service


@app.middleware("http")
async def reject_non_notification_mutations(request, call_next):
    """Keep browser acceptance incapable of mutating any financial domain."""
    if request.method not in {"GET", "OPTIONS"} and not request.url.path.startswith(
        "/api/v1/notifications"
    ):
        return JSONResponse(
            status_code=409,
            content={"detail": "SPRINT29_ACCEPTANCE_FINANCIAL_MUTATION_BLOCKED"},
        )
    return await call_next(request)
