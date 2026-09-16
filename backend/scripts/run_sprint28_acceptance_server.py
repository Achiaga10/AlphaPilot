"""Run a local acceptance server against TEST_DATABASE_URL only."""

from __future__ import annotations

import argparse
import asyncio
import os

import uvicorn

os.environ["DEBUG"] = "false"

from alphapilot.core.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--broker-state",
        choices=["disabled", "misconfigured"],
        default="disabled",
    )
    args = parser.parse_args()
    if settings.TEST_DATABASE_URL is None:
        raise RuntimeError("TEST_DATABASE_URL is required")
    if settings.TEST_DATABASE_URL == settings.DATABASE_URL:
        raise RuntimeError("Acceptance server refuses the development database")
    settings.DEBUG = False
    settings.DATABASE_URL = settings.TEST_DATABASE_URL
    settings.CORS_ORIGINS = "http://127.0.0.1:5180"
    settings.ALPACA_SYNC_ENABLED = args.broker_state == "misconfigured"
    if args.broker_state == "misconfigured":
        settings.ALPACA_API_KEY = ""
        settings.ALPACA_SECRET_KEY = ""
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    config = uvicorn.Config(
        "alphapilot.main:app",
        host="127.0.0.1",
        port=8010,
        loop="none",
    )
    server = uvicorn.Server(config)
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
