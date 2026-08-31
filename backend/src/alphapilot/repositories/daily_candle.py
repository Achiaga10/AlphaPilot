from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.daily_candle_version import DailyCandleVersion
from alphapilot.market.provenance import CandleUpsertResult, CandleVersionProvenance
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.base import BaseRepository


class DailyCandleRepository(BaseRepository[DailyCandle]):
    UPSERT_CHUNK_SIZE = 1000

    def __init__(
        self,
        session: AsyncSession,
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        super().__init__(
            session,
            DailyCandle,
        )
        self.session_policy = session_policy or CompletedDailySessionPolicy()

    async def get_history(
        self,
        company_id: UUID,
        start: date,
        end: date,
    ) -> list[DailyCandle]:
        result = await self.session.execute(
            select(DailyCandle)
            .where(
                DailyCandle.company_id == company_id,
                DailyCandle.trading_day >= start,
                DailyCandle.trading_day <= end,
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
            .order_by(DailyCandle.trading_day),
        )

        return list(result.scalars().all())

    async def get_histories(
        self,
        company_ids: list[UUID],
        start: date,
        end: date,
    ) -> dict[UUID, list[DailyCandle]]:
        """Load one completed-session history window for many companies."""
        if not company_ids:
            return {}
        result = await self.session.execute(
            select(DailyCandle)
            .where(
                DailyCandle.company_id.in_(company_ids),
                DailyCandle.trading_day >= start,
                DailyCandle.trading_day <= end,
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
            .order_by(DailyCandle.company_id, DailyCandle.trading_day)
        )
        histories: defaultdict[UUID, list[DailyCandle]] = defaultdict(list)
        for candle in result.scalars().all():
            histories[candle.company_id].append(candle)
        return dict(histories)

    async def get_latest(self, company_id: UUID) -> DailyCandle | None:
        result = await self.session.execute(
            select(DailyCandle)
            .where(
                DailyCandle.company_id == company_id,
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
            .order_by(DailyCandle.trading_day.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_many(self, company_ids: list[UUID]) -> dict[UUID, DailyCandle]:
        if not company_ids:
            return {}
        ranked = (
            select(
                DailyCandle.id.label("candle_id"),
                func.row_number()
                .over(
                    partition_by=DailyCandle.company_id,
                    order_by=DailyCandle.trading_day.desc(),
                )
                .label("row_number"),
            )
            .where(
                DailyCandle.company_id.in_(company_ids),
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
            .subquery()
        )
        result = await self.session.execute(
            select(DailyCandle)
            .join(ranked, ranked.c.candle_id == DailyCandle.id)
            .where(ranked.c.row_number == 1)
        )
        return {item.company_id: item for item in result.scalars().all()}

    async def get_for_day(self, company_id: UUID, trading_day: date) -> DailyCandle | None:
        result = await self.session.execute(
            select(DailyCandle).where(
                DailyCandle.company_id == company_id,
                DailyCandle.trading_day == trading_day,
            )
        )
        return result.scalar_one_or_none()

    async def get_versions(self, company_id: UUID, trading_day: date) -> list[DailyCandleVersion]:
        result = await self.session.execute(
            select(DailyCandleVersion)
            .where(
                DailyCandleVersion.company_id == company_id,
                DailyCandleVersion.trading_day == trading_day,
            )
            .order_by(DailyCandleVersion.version_sequence)
        )
        return list(result.scalars().all())

    async def upsert_many(
        self,
        candles: list[DailyCandle],
        *,
        provenance: CandleVersionProvenance | None = None,
    ) -> CandleUpsertResult:
        candles = [
            candle for candle in candles if self.session_policy.is_complete(candle.trading_day)
        ]
        if not candles:
            return CandleUpsertResult(0, 0, 0, 0)

        # A provider should not emit duplicates, but normalizing by identity
        # keeps comparison/version sequencing deterministic if it does.
        by_key = {(candle.company_id, candle.trading_day): candle for candle in candles}
        candles = [by_key[key] for key in sorted(by_key, key=lambda item: (str(item[0]), item[1]))]
        effective_provenance = provenance or CandleVersionProvenance.legacy_unknown()

        operational_changed = 0
        versions_created = 0
        unchanged = 0

        for chunk_start in range(
            0,
            len(candles),
            self.UPSERT_CHUNK_SIZE,
        ):
            candle_chunk = candles[chunk_start : chunk_start + self.UPSERT_CHUNK_SIZE]
            keys = [(candle.company_id, candle.trading_day) for candle in candle_chunk]
            existing_result = await self.session.execute(
                select(DailyCandle).where(
                    tuple_(DailyCandle.company_id, DailyCandle.trading_day).in_(keys)
                )
            )
            existing_by_key = {
                (item.company_id, item.trading_day): item
                for item in existing_result.scalars().all()
            }
            version_result = await self.session.execute(
                select(DailyCandleVersion)
                .where(
                    tuple_(
                        DailyCandleVersion.company_id,
                        DailyCandleVersion.trading_day,
                    ).in_(keys)
                )
                .order_by(
                    DailyCandleVersion.company_id,
                    DailyCandleVersion.trading_day,
                    DailyCandleVersion.version_sequence.desc(),
                )
            )
            latest_versions: dict[tuple[UUID, date], DailyCandleVersion] = {}
            for version in version_result.scalars().all():
                latest_versions.setdefault((version.company_id, version.trading_day), version)

            operational_values: list[dict[str, object]] = []
            version_values: list[dict[str, object]] = []
            for candle in candle_chunk:
                key = (candle.company_id, candle.trading_day)
                existing = existing_by_key.get(key)
                latest = latest_versions.get(key)
                next_sequence = (latest.version_sequence + 1) if latest else 1

                # Direct pre-Sprint13/test inserts may exist without history.
                # Preserve their current value honestly before considering the
                # newly observed provider value.
                if existing is not None and latest is None:
                    legacy = CandleVersionProvenance.legacy_unknown(
                        observed_at=existing.updated_at or existing.created_at
                    )
                    version_values.append(
                        self._version_values(existing, legacy, version_sequence=1)
                    )
                    versions_created += 1
                    next_sequence = 2

                if existing is not None and self._same_research_values(existing, candle):
                    unchanged += 1
                    continue

                operational_values.append(self._operational_values(candle))
                version_values.append(
                    self._version_values(
                        candle,
                        effective_provenance,
                        version_sequence=next_sequence,
                    )
                )
                operational_changed += 1
                versions_created += 1

            if version_values:
                await self.session.execute(insert(DailyCandleVersion).values(version_values))

            if not operational_values:
                continue

            statement = insert(DailyCandle).values(operational_values)

            statement = statement.on_conflict_do_update(
                index_elements=[
                    DailyCandle.company_id,
                    DailyCandle.trading_day,
                ],
                set_={
                    "open": statement.excluded.open,
                    "high": statement.excluded.high,
                    "low": statement.excluded.low,
                    "close": statement.excluded.close,
                    "volume": statement.excluded.volume,
                    "updated_at": func.now(),
                },
            )

            await self.session.execute(statement)

        await self.session.commit()
        return CandleUpsertResult(
            checked=len(candles),
            operational_rows_changed=operational_changed,
            versions_created=versions_created,
            unchanged=unchanged,
        )

    @staticmethod
    def _same_research_values(left: DailyCandle, right: DailyCandle) -> bool:
        return (
            Decimal(left.open) == Decimal(right.open)
            and Decimal(left.high) == Decimal(right.high)
            and Decimal(left.low) == Decimal(right.low)
            and Decimal(left.close) == Decimal(right.close)
            and int(left.volume) == int(right.volume)
        )

    @staticmethod
    def _operational_values(candle: DailyCandle) -> dict[str, object]:
        return {
            "company_id": candle.company_id,
            "trading_day": candle.trading_day,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }

    @staticmethod
    def _version_values(
        candle: DailyCandle,
        provenance: CandleVersionProvenance,
        *,
        version_sequence: int,
    ) -> dict[str, object]:
        return {
            "company_id": candle.company_id,
            "trading_day": candle.trading_day,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "provider": provenance.provider,
            "feed": provenance.feed,
            "provenance_status": provenance.status.value,
            "ingestion_batch_id": provenance.ingestion_batch_id,
            "observed_at": provenance.observed_at,
            "version_sequence": version_sequence,
        }
