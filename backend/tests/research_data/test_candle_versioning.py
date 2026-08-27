from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.daily_candle_version import DailyCandleVersion
from alphapilot.database.models.market_data_ingestion import (
    CandleProvenanceStatus,
    IngestionBatchStatus,
    MarketDataIngestionBatch,
)
from alphapilot.market.provenance import CandleVersionProvenance
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.market_data_ingestion import MarketDataIngestionBatchRepository
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService


def make_candle(company_id: object, close: str, volume: int = 1000) -> DailyCandle:
    return DailyCandle(
        company_id=company_id,
        trading_day=date(2025, 1, 2),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=volume,
    )


async def company(db_session: AsyncSession) -> Company:
    item = Company(
        id=uuid4(),
        ticker="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector="Information Technology",
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    return item


async def batch_and_provenance(
    db_session: AsyncSession,
) -> tuple[MarketDataIngestionBatchService, MarketDataIngestionBatch, CandleVersionProvenance]:
    service = MarketDataIngestionBatchService(MarketDataIngestionBatchRepository(db_session))
    batch = await service.start(
        provider="alpaca",
        feed="iex",
        timeframe="1Day",
        adjustment="split",
        requested_start=date(2025, 1, 2),
        requested_end=date(2025, 1, 2),
        symbols_requested=1,
        request_metadata={
            "sort": "asc",
            "APCA-API-KEY-ID": "must-not-persist",
            "authorization": "must-not-persist",
        },
    )
    provenance = CandleVersionProvenance(
        provider="alpaca",
        feed="iex",
        ingestion_batch_id=batch.id,
        observed_at=datetime(2025, 1, 3, tzinfo=UTC),
        status=CandleProvenanceStatus.COMPLETE,
    )
    return service, batch, provenance


@pytest.mark.asyncio
async def test_batch_records_provenance_safely_and_becomes_terminal(
    db_session: AsyncSession,
) -> None:
    service, batch, _ = await batch_and_provenance(db_session)
    assert batch.provider == "alpaca"
    assert batch.feed == "iex"
    assert batch.request_metadata == {"sort": "asc"}
    completed = await service.complete(batch, succeeded=1, failed=0)
    assert completed.status == IngestionBatchStatus.COMPLETED.value
    assert completed.completed_at is not None
    with pytest.raises(ValueError, match="already terminal"):
        await service.complete(completed, succeeded=1, failed=0)


@pytest.mark.asyncio
async def test_failed_batch_records_terminal_failure(db_session: AsyncSession) -> None:
    service, batch, _ = await batch_and_provenance(db_session)
    failed = await service.fail(batch, failed=1)
    assert failed.status == IngestionBatchStatus.FAILED.value
    assert failed.symbols_failed == 1


@pytest.mark.asyncio
async def test_new_unchanged_changed_ohlc_and_volume_versions(
    db_session: AsyncSession,
) -> None:
    item = await company(db_session)
    repository = DailyCandleRepository(db_session)
    batch_service, batch, provenance = await batch_and_provenance(db_session)

    first = await repository.upsert_many([make_candle(item.id, "101")], provenance=provenance)
    assert first.operational_rows_changed == 1
    assert first.versions_created == 1
    unchanged = await repository.upsert_many(
        [make_candle(item.id, "101.0000")], provenance=provenance
    )
    assert unchanged.operational_rows_changed == 0
    assert unchanged.versions_created == 0
    assert unchanged.unchanged == 1

    changed_close = await repository.upsert_many(
        [make_candle(item.id, "102")], provenance=provenance
    )
    changed_volume = await repository.upsert_many(
        [make_candle(item.id, "102", volume=1001)], provenance=provenance
    )
    assert changed_close.versions_created == 1
    assert changed_volume.versions_created == 1
    versions = await repository.get_versions(item.id, date(2025, 1, 2))
    assert [version.version_sequence for version in versions] == [1, 2, 3]
    assert [version.close for version in versions] == [
        Decimal("101.0000"),
        Decimal("102.0000"),
        Decimal("102.0000"),
    ]
    assert [version.volume for version in versions] == [1000, 1000, 1001]
    assert all(version.provider == "alpaca" for version in versions)
    assert all(version.feed == "iex" for version in versions)
    latest = await repository.get_for_day(item.id, date(2025, 1, 2))
    assert latest is not None
    assert latest.close == Decimal("102.0000")
    assert latest.volume == 1001
    await batch_service.complete(batch, succeeded=1, failed=0)


@pytest.mark.asyncio
async def test_direct_existing_candle_gets_honest_legacy_version_once(
    db_session: AsyncSession,
) -> None:
    item = await company(db_session)
    direct = make_candle(item.id, "101")
    db_session.add(direct)
    await db_session.commit()
    repository = DailyCandleRepository(db_session)
    first = await repository.upsert_many([make_candle(item.id, "101")])
    second = await repository.upsert_many([make_candle(item.id, "101")])
    assert first.versions_created == 1
    assert second.versions_created == 0
    versions = await repository.get_versions(item.id, date(2025, 1, 2))
    assert len(versions) == 1
    assert versions[0].provenance_status == CandleProvenanceStatus.LEGACY_UNKNOWN.value
    assert versions[0].provider == "LEGACY_UNKNOWN"
    assert versions[0].feed == "UNKNOWN"
    assert versions[0].close == Decimal("101.0000")


@pytest.mark.asyncio
async def test_incomplete_session_creates_neither_operational_nor_version(
    db_session: AsyncSession,
) -> None:
    item = await company(db_session)
    policy = CompletedDailySessionPolicy(
        now_provider=lambda: datetime(2026, 8, 27, 18, 0, tzinfo=UTC)
    )
    repository = DailyCandleRepository(db_session, policy)
    incomplete = make_candle(item.id, "101")
    incomplete.trading_day = date(2026, 8, 27)
    result = await repository.upsert_many([incomplete])
    assert result.checked == 0
    assert await repository.get_for_day(item.id, date(2026, 8, 27)) is None
    versions = await db_session.execute(select(DailyCandleVersion))
    assert list(versions.scalars()) == []


@pytest.mark.asyncio
async def test_candle_versions_are_database_immutable(db_session: AsyncSession) -> None:
    item = await company(db_session)
    repository = DailyCandleRepository(db_session)
    batch_service, batch, provenance = await batch_and_provenance(db_session)
    await repository.upsert_many([make_candle(item.id, "101")], provenance=provenance)
    await batch_service.complete(batch, succeeded=1, failed=0)
    version = (await repository.get_versions(item.id, date(2025, 1, 2)))[0]
    version.close = Decimal("999")

    with pytest.raises(DBAPIError, match="DailyCandleVersion rows are immutable"):
        await db_session.commit()
    await db_session.rollback()
