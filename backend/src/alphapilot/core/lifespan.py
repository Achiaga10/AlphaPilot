from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from alphapilot.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    configure_logging()

    print("AlphaPilot started")

    yield

    print("AlphaPilot stopped")
