import asyncio

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import AsyncSessionLocal
from alphapilot.main import app

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
