from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from alphapilot.backtesting.service import CandleHistoryService, CompanyLookupService
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.database.models.research_dataset import (
    ResearchDatasetMemberRole,
    ResearchDatasetStatus,
)
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.schemas.research_dataset import ResearchDatasetManifestSchema


class ResearchMarketDataSource(Protocol):
    async def get_company(self, ticker: str) -> Company | None: ...

    async def get_history(self, company_id: UUID, start: date, end: date) -> list[DailyCandle]: ...

    async def list_active(self, index_symbol: str) -> list[IndexConstituent]: ...

    async def manifest(self) -> ResearchDatasetManifestSchema | None: ...


@dataclass(slots=True, frozen=True)
class ResearchDataRunMetadata:
    data_mode: str
    dataset_snapshot_id: UUID | None
    dataset_sha256: str | None
    universe_sha256: str | None
    provenance_status: str
    snapshot_git_revision: str | None
    snapshot_git_dirty: bool | None
    run_git_revision: str
    run_git_dirty: bool


class OperationalMarketDataSource:
    def __init__(
        self,
        company_service: CompanyLookupService,
        candle_service: CandleHistoryService,
        universe_repository: IndexConstituentRepository,
    ) -> None:
        self.company_service = company_service
        self.candle_service = candle_service
        self.universe_repository = universe_repository

    async def get_company(self, ticker: str) -> Company | None:
        return await self.company_service.get_company(ticker)

    async def get_history(self, company_id: UUID, start: date, end: date) -> list[DailyCandle]:
        return await self.candle_service.get_history(company_id, start, end)

    async def list_active(self, index_symbol: str) -> list[IndexConstituent]:
        return await self.universe_repository.list_active(index_symbol)

    async def manifest(self) -> ResearchDatasetManifestSchema | None:
        return None


class FrozenDatasetMarketDataSource:
    def __init__(self, repository: ResearchDatasetRepository, snapshot_id: UUID) -> None:
        self.repository = repository
        self.snapshot_id = snapshot_id

    async def get_company(self, ticker: str) -> Company | None:
        member = await self.repository.get_member(self.snapshot_id, ticker)
        if member is None:
            return None
        return Company(
            id=member.company_id,
            ticker=member.ticker_at_snapshot,
            name=member.company_name_at_snapshot,
            exchange=member.exchange_at_snapshot,
            sector=member.sector_at_snapshot,
            is_active=True,
        )

    async def get_history(self, company_id: UUID, start: date, end: date) -> list[DailyCandle]:
        return await self.repository.get_frozen_history(self.snapshot_id, company_id, start, end)

    async def list_active(self, index_symbol: str) -> list[IndexConstituent]:
        del index_symbol
        members = await self.repository.list_members(
            self.snapshot_id, role=ResearchDatasetMemberRole.UNIVERSE
        )
        return [
            IndexConstituent(
                index_symbol="FROZEN_SNAPSHOT",
                ticker=member.ticker_at_snapshot,
                is_active=True,
            )
            for member in members
        ]

    async def manifest(self) -> ResearchDatasetManifestSchema:
        snapshot = await self.repository.get(self.snapshot_id)
        if snapshot is None or snapshot.status != ResearchDatasetStatus.FINALIZED.value:
            raise ValueError(f"Finalized research dataset {self.snapshot_id} not found")
        return ResearchDatasetManifestSchema.model_validate(snapshot)
