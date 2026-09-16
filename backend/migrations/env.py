import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alphapilot.core.config import settings
from alphapilot.database.base import Base

# Import all models here so Alembic can discover them
from alphapilot.database.models import (  # noqa: F401
    broker_sync,
    company,
    daily_candle,
    daily_candle_version,
    external_execution,
    forward_portfolio,
    index_constituent,
    market_data_ingestion,
    operations,
    research_dataset,
    research_portfolio,
)

config = context.config

database_url = settings.DATABASE_URL
if os.getenv("ALPHAPILOT_MIGRATION_USE_TEST_DATABASE") == "true":
    if settings.TEST_DATABASE_URL is None:
        raise RuntimeError("TEST_DATABASE_URL is required for isolated migration verification")
    if settings.TEST_DATABASE_URL == settings.DATABASE_URL:
        raise RuntimeError("Refusing to run test migration against the development database")
    database_url = settings.TEST_DATABASE_URL

config.set_main_option(
    "sqlalchemy.url",
    database_url,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_migrations_online())
