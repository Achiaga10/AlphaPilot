import asyncio

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import AsyncSessionLocal, get_db
from alphapilot.main import app

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
    ) as client:
        yield client

    app.dependency_overrides.clear()
