from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import case, func, insert, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.daily_candle_version import DailyCandleVersion
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.database.models.market_data_ingestion import (
    CandleProvenanceStatus,
    IngestionBatchStatus,
    MarketDataIngestionBatch,
)
from alphapilot.database.models.research_dataset import (
    ResearchDatasetCandleMember,
    ResearchDatasetMemberRole,
    ResearchDatasetProvenanceStatus,
    ResearchDatasetSnapshot,
    ResearchDatasetStatus,
    ResearchDatasetUniverseMember,
)
from alphapilot.research_data.hashing import CanonicalCandleRow


class ResearchDatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_current_universe_companies(self, index_symbol: str) -> list[Company]:
        result = await self.session.execute(
            select(Company)
            .join(IndexConstituent, IndexConstituent.ticker == Company.ticker)
            .where(
                IndexConstituent.index_symbol == index_symbol.upper(),
                IndexConstituent.is_active.is_(True),
                Company.is_active.is_(True),
            )
            .order_by(Company.ticker)
        )
        return list(result.scalars().all())

    async def list_companies_by_tickers(self, tickers: Sequence[str]) -> list[Company]:
        normalized = sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})
        result = await self.session.execute(
            select(Company).where(Company.ticker.in_(normalized)).order_by(Company.ticker)
        )
        return list(result.scalars().all())

    async def create_snapshot(self, snapshot: ResearchDatasetSnapshot) -> None:
        self.session.add(snapshot)
        await self.session.flush()

    async def add_universe_members(self, members: Sequence[ResearchDatasetUniverseMember]) -> None:
        self.session.add_all(members)
        await self.session.flush()

    async def freeze_latest_versions(self, snapshot: ResearchDatasetSnapshot) -> int:
        ranked = (
            select(
                DailyCandleVersion.id.label("candle_version_id"),
                DailyCandleVersion.company_id.label("company_id"),
                DailyCandleVersion.trading_day.label("trading_day"),
                ResearchDatasetUniverseMember.ticker_at_snapshot.label("ticker_at_snapshot"),
                func.row_number()
                .over(
                    partition_by=(
                        DailyCandleVersion.company_id,
                        DailyCandleVersion.trading_day,
                    ),
                    order_by=(
                        DailyCandleVersion.version_sequence.desc(),
                        DailyCandleVersion.observed_at.desc(),
                    ),
                )
                .label("version_rank"),
            )
            .join(
                ResearchDatasetUniverseMember,
                ResearchDatasetUniverseMember.company_id == DailyCandleVersion.company_id,
            )
            .where(
                ResearchDatasetUniverseMember.snapshot_id == snapshot.id,
                DailyCandleVersion.trading_day >= snapshot.requested_start,
                DailyCandleVersion.trading_day <= snapshot.requested_end,
                DailyCandleVersion.observed_at <= snapshot.version_watermark_at,
            )
            .subquery()
        )
        member_select = select(
            literal(snapshot.id),
            ranked.c.candle_version_id,
            ranked.c.company_id,
            ranked.c.ticker_at_snapshot,
            ranked.c.trading_day,
        ).where(ranked.c.version_rank == 1)
        statement = insert(ResearchDatasetCandleMember).from_select(
            [
                "snapshot_id",
                "candle_version_id",
                "company_id",
                "ticker_at_snapshot",
                "trading_day",
            ],
            member_select,
        )
        await self.session.execute(statement)
        await self.session.flush()
        count_result = await self.session.execute(
            select(func.count())
            .select_from(ResearchDatasetCandleMember)
            .where(ResearchDatasetCandleMember.snapshot_id == snapshot.id)
        )
        return int(count_result.scalar_one())

    async def stream_canonical_rows(self, snapshot_id: UUID) -> AsyncIterator[CanonicalCandleRow]:
        statement = (
            select(
                ResearchDatasetCandleMember.ticker_at_snapshot,
                DailyCandleVersion.trading_day,
                DailyCandleVersion.open,
                DailyCandleVersion.high,
                DailyCandleVersion.low,
                DailyCandleVersion.close,
                DailyCandleVersion.volume,
            )
            .join(
                DailyCandleVersion,
                DailyCandleVersion.id == ResearchDatasetCandleMember.candle_version_id,
            )
            .where(ResearchDatasetCandleMember.snapshot_id == snapshot_id)
            .order_by(
                ResearchDatasetCandleMember.ticker_at_snapshot,
                DailyCandleVersion.trading_day,
            )
            .execution_options(yield_per=5000)
        )
        result = await self.session.stream(statement)
        async for row in result:
            yield CanonicalCandleRow(
                ticker=row[0],
                trading_day=row[1],
                open=row[2],
                high=row[3],
                low=row[4],
                close=row[5],
                volume=row[6],
            )

    async def snapshot_statistics(
        self, snapshot_id: UUID
    ) -> tuple[int, int, date | None, date | None, str]:
        result = await self.session.execute(
            select(
                func.count(ResearchDatasetCandleMember.candle_version_id),
                func.count(func.distinct(ResearchDatasetCandleMember.company_id)),
                func.min(ResearchDatasetCandleMember.trading_day),
                func.max(ResearchDatasetCandleMember.trading_day),
                func.sum(
                    case(
                        (
                            or_(
                                DailyCandleVersion.provenance_status
                                != CandleProvenanceStatus.COMPLETE.value,
                                DailyCandleVersion.ingestion_batch_id.is_(None),
                                MarketDataIngestionBatch.status
                                != IngestionBatchStatus.COMPLETED.value,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .join(
                DailyCandleVersion,
                DailyCandleVersion.id == ResearchDatasetCandleMember.candle_version_id,
            )
            .outerjoin(
                MarketDataIngestionBatch,
                MarketDataIngestionBatch.id == DailyCandleVersion.ingestion_batch_id,
            )
            .where(ResearchDatasetCandleMember.snapshot_id == snapshot_id)
        )
        row = result.one()
        count = int(row[0] or 0)
        legacy_count = int(row[4] or 0)
        provenance = (
            ResearchDatasetProvenanceStatus.UNKNOWN.value
            if count == 0
            else (
                ResearchDatasetProvenanceStatus.LEGACY_PARTIAL.value
                if legacy_count
                else ResearchDatasetProvenanceStatus.COMPLETE.value
            )
        )
        return count, int(row[1] or 0), row[2], row[3], provenance

    async def finalize(self, snapshot: ResearchDatasetSnapshot) -> None:
        if snapshot.status != ResearchDatasetStatus.DRAFT.value:
            raise ValueError("Only a draft research dataset can be finalized")
        snapshot.status = ResearchDatasetStatus.FINALIZED.value
        await self.session.commit()
        await self.session.refresh(snapshot)

    async def get(self, snapshot_id: UUID) -> ResearchDatasetSnapshot | None:
        return await self.session.get(ResearchDatasetSnapshot, snapshot_id)

    async def list_snapshots(self) -> list[ResearchDatasetSnapshot]:
        result = await self.session.execute(
            select(ResearchDatasetSnapshot).order_by(ResearchDatasetSnapshot.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_members(
        self, snapshot_id: UUID, *, role: ResearchDatasetMemberRole | None = None
    ) -> list[ResearchDatasetUniverseMember]:
        statement = select(ResearchDatasetUniverseMember).where(
            ResearchDatasetUniverseMember.snapshot_id == snapshot_id
        )
        if role is not None:
            statement = statement.where(ResearchDatasetUniverseMember.role == role.value)
        result = await self.session.execute(
            statement.order_by(ResearchDatasetUniverseMember.ticker_at_snapshot)
        )
        return list(result.scalars().all())

    async def get_member(
        self, snapshot_id: UUID, ticker: str
    ) -> ResearchDatasetUniverseMember | None:
        result = await self.session.execute(
            select(ResearchDatasetUniverseMember).where(
                ResearchDatasetUniverseMember.snapshot_id == snapshot_id,
                ResearchDatasetUniverseMember.ticker_at_snapshot == ticker.strip().upper(),
            )
        )
        return result.scalar_one_or_none()

    async def get_frozen_history(
        self, snapshot_id: UUID, company_id: UUID, start: date, end: date
    ) -> list[DailyCandle]:
        result = await self.session.execute(
            select(DailyCandleVersion)
            .join(
                ResearchDatasetCandleMember,
                ResearchDatasetCandleMember.candle_version_id == DailyCandleVersion.id,
            )
            .where(
                ResearchDatasetCandleMember.snapshot_id == snapshot_id,
                ResearchDatasetCandleMember.company_id == company_id,
                DailyCandleVersion.trading_day >= start,
                DailyCandleVersion.trading_day <= end,
            )
            .order_by(DailyCandleVersion.trading_day)
        )
        return [
            DailyCandle(
                company_id=item.company_id,
                trading_day=item.trading_day,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=item.volume,
            )
            for item in result.scalars().all()
        ]
