from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.market_data_ingestion import (
    IngestionBatchStatus,
    MarketDataIngestionBatch,
)


class MarketDataIngestionBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, batch: MarketDataIngestionBatch) -> MarketDataIngestionBatch:
        self.session.add(batch)
        await self.session.commit()
        await self.session.refresh(batch)
        return batch

    async def get(self, batch_id: UUID) -> MarketDataIngestionBatch | None:
        return await self.session.get(MarketDataIngestionBatch, batch_id)

    async def latest(self) -> MarketDataIngestionBatch | None:
        result = await self.session.execute(
            select(MarketDataIngestionBatch)
            .order_by(MarketDataIngestionBatch.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, *, limit: int = 50) -> list[MarketDataIngestionBatch]:
        result = await self.session.execute(
            select(MarketDataIngestionBatch)
            .order_by(MarketDataIngestionBatch.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def finalize(
        self,
        batch: MarketDataIngestionBatch,
        *,
        status: IngestionBatchStatus,
        succeeded: int,
        failed: int,
    ) -> MarketDataIngestionBatch:
        if batch.status != IngestionBatchStatus.RUNNING.value:
            raise ValueError("Ingestion batch is already terminal")
        if status == IngestionBatchStatus.RUNNING:
            raise ValueError("Terminal ingestion status is required")
        batch.status = status.value
        batch.symbols_succeeded = succeeded
        batch.symbols_failed = failed
        batch.completed_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(batch)
        return batch
