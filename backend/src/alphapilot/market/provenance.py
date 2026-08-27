from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from alphapilot.database.models.market_data_ingestion import CandleProvenanceStatus


@dataclass(slots=True, frozen=True)
class CandleVersionProvenance:
    provider: str
    feed: str
    ingestion_batch_id: UUID | None
    observed_at: datetime
    status: CandleProvenanceStatus

    @classmethod
    def legacy_unknown(cls, *, observed_at: datetime | None = None) -> CandleVersionProvenance:
        return cls(
            provider="LEGACY_UNKNOWN",
            feed="UNKNOWN",
            ingestion_batch_id=None,
            observed_at=observed_at or datetime.now(UTC),
            status=CandleProvenanceStatus.LEGACY_UNKNOWN,
        )


@dataclass(slots=True, frozen=True)
class CandleUpsertResult:
    checked: int
    operational_rows_changed: int
    versions_created: int
    unchanged: int
