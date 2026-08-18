import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from alphapilot.core.config import settings
from alphapilot.database.session import get_db
from alphapilot.main import app

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


if settings.TEST_DATABASE_URL is None:
    raise RuntimeError(
        "TEST_DATABASE_URL is not configured. "
        "Refusing to run tests without a dedicated test database."
    )

if settings.TEST_DATABASE_URL == settings.DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL must be different from DATABASE_URL. "
        "Refusing to run tests against the development database."
    )

TEST_DATABASE_URL = settings.TEST_DATABASE_URL


test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)


TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_test_database() -> AsyncGenerator[None, None]:
    async with TestSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE companies CASCADE"))
        await session.commit()

    yield

    async with TestSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE companies CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[
        AsyncSession,
        None,
    ]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(
        app=app,
    )

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=True,
        ) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )
