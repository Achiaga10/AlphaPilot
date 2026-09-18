"""Run the controlled Sprint 29 FastAPI acceptance app on Windows."""

from __future__ import annotations

import asyncio

import uvicorn
from sprint29_acceptance_app import app

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

uvicorn.run(
    app,
    host="127.0.0.1",
    port=8010,
    loop="asyncio",
)
