from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from alphapilot.database.models.market_data_ingestion import (
    IngestionBatchStatus,
    MarketDataIngestionBatch,
)
from alphapilot.repositories.market_data_ingestion import MarketDataIngestionBatchRepository


class MarketDataIngestionBatchService:
    """Creates sanitized provider-request provenance and finalizes it once."""

    FORBIDDEN_METADATA_KEYS = {
        "api_key",
        "apikey",
        "authorization",
        "secret",
        "token",
        "password",
    }

    def __init__(self, repository: MarketDataIngestionBatchRepository) -> None:
        self.repository = repository

    async def start(
        self,
        *,
        provider: str,
        feed: str,
        timeframe: str,
        adjustment: str,
        requested_start: date,
        requested_end: date,
        symbols_requested: int,
        benchmark_ticker: str | None = None,
        request_metadata: dict[str, object] | None = None,
    ) -> MarketDataIngestionBatch:
        if requested_start > requested_end:
            raise ValueError("requested_start must not exceed requested_end")
        metadata = self._sanitize_metadata(request_metadata or {})
        return await self.repository.create(
            MarketDataIngestionBatch(
                provider=provider.strip().lower(),
                feed=feed.strip().lower(),
                timeframe=timeframe,
                adjustment=adjustment,
                requested_start=requested_start,
                requested_end=requested_end,
                benchmark_ticker=(benchmark_ticker.strip().upper() if benchmark_ticker else None),
                request_metadata=metadata,
                symbols_requested=symbols_requested,
                symbols_succeeded=0,
                symbols_failed=0,
                status=IngestionBatchStatus.RUNNING.value,
                created_at=datetime.now(UTC),
            )
        )

    async def complete(
        self, batch: MarketDataIngestionBatch, *, succeeded: int, failed: int
    ) -> MarketDataIngestionBatch:
        return await self.repository.finalize(
            batch,
            status=IngestionBatchStatus.COMPLETED,
            succeeded=succeeded,
            failed=failed,
        )

    async def fail(
        self, batch: MarketDataIngestionBatch, *, succeeded: int = 0, failed: int
    ) -> MarketDataIngestionBatch:
        return await self.repository.finalize(
            batch,
            status=IngestionBatchStatus.FAILED,
            succeeded=succeeded,
            failed=failed,
        )

    async def fail_after_error(
        self, batch_id: UUID, *, succeeded: int = 0, failed: int
    ) -> MarketDataIngestionBatch:
        """Recover the transaction after a write error and leave the batch terminal."""

        await self.repository.session.rollback()
        batch = await self.repository.get(batch_id)
        if batch is None:
            raise RuntimeError(f"Ingestion batch {batch_id} disappeared after rollback")
        return await self.fail(batch, succeeded=succeeded, failed=failed)

    @classmethod
    def _sanitize_metadata(cls, metadata: dict[str, object]) -> dict[str, object]:
        sanitized: dict[str, object] = {}
        for key, value in metadata.items():
            normalized = key.strip().lower().replace("-", "_")
            if any(fragment in normalized for fragment in cls.FORBIDDEN_METADATA_KEYS):
                continue
            sanitized[key] = value
        return sanitized
