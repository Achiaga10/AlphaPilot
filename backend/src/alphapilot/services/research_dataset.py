from __future__ import annotations

import hashlib
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.research_dataset import (
    ResearchDatasetMemberRole,
    ResearchDatasetProvenanceStatus,
    ResearchDatasetSnapshot,
    ResearchDatasetStatus,
    ResearchDatasetUniverseMember,
)
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.research_data.hashing import canonical_candle_line, hash_universe
from alphapilot.schemas.research_dataset import (
    ResearchDatasetManifestSchema,
    ResearchDatasetVerificationSchema,
)


@dataclass(slots=True, frozen=True)
class GitRevision:
    head: str
    dirty: bool


def capture_git_revision() -> GitRevision:
    repository_root = Path(__file__).resolve().parents[4]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty_output = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return GitRevision(head=head, dirty=bool(dirty_output.strip()))


class ResearchDatasetVerificationError(RuntimeError):
    pass


class ResearchDatasetService:
    CURRENT_UNIVERSE = "CURRENT_RESEARCH_UNIVERSE"
    EXPLICIT_TICKERS = "EXPLICIT_TICKERS"
    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        repository: ResearchDatasetRepository,
        *,
        git_revision_provider: Callable[[], GitRevision] = capture_git_revision,
    ) -> None:
        self.repository = repository
        self.git_revision_provider = git_revision_provider

    async def create_snapshot(
        self,
        *,
        start: date,
        end: date,
        universe_mode: str = CURRENT_UNIVERSE,
        tickers: Sequence[str] | None = None,
        benchmark_ticker: str = "SPY",
        label: str | None = None,
        provider_expectation: str | None = None,
        feed_expectation: str | None = None,
        notes: str | None = None,
    ) -> ResearchDatasetManifestSchema:
        if start > end:
            raise ValueError("start must not exceed end")
        started = time.perf_counter()
        watermark = datetime.now(UTC)
        benchmark = benchmark_ticker.strip().upper()
        if universe_mode == self.CURRENT_UNIVERSE:
            companies = await self.repository.list_current_universe_companies(
                self.SP500_INDEX_SYMBOL
            )
            universe_identifier = f"FROZEN_CURRENT_UNIVERSE:{self.SP500_INDEX_SYMBOL}"
            membership_source = f"CURRENT_ACTIVE:{self.SP500_INDEX_SYMBOL}"
        elif universe_mode == self.EXPLICIT_TICKERS:
            requested = sorted(
                {
                    ticker.strip().upper()
                    for ticker in (tickers or ())
                    if ticker.strip() and ticker.strip().upper() != benchmark
                }
            )
            if not requested:
                raise ValueError("Explicit snapshot tickers must not be empty")
            companies = await self.repository.list_companies_by_tickers(requested)
            found = {company.ticker.upper() for company in companies}
            missing = sorted(set(requested) - found)
            if missing:
                raise ValueError(f"Companies not found: {', '.join(missing)}")
            universe_identifier = "EXPLICIT_TICKERS"
            membership_source = "EXPLICIT_REQUEST"
        else:
            raise ValueError(f"Unsupported universe mode: {universe_mode}")

        benchmark_rows = await self.repository.list_companies_by_tickers([benchmark])
        if not benchmark_rows:
            raise ValueError(f"Benchmark company {benchmark} not found")
        benchmark_company = benchmark_rows[0]
        companies = [company for company in companies if company.ticker.upper() != benchmark]
        git_revision = self.git_revision_provider()
        snapshot = ResearchDatasetSnapshot(
            label=label,
            status=ResearchDatasetStatus.DRAFT.value,
            created_at=watermark,
            version_watermark_at=watermark,
            provider_expectation=(
                provider_expectation.strip().lower() if provider_expectation else None
            ),
            feed_expectation=(feed_expectation.strip().lower() if feed_expectation else None),
            timeframe="1Day",
            adjustment="split",
            requested_start=start,
            requested_end=end,
            benchmark_ticker=benchmark,
            universe_identifier=universe_identifier,
            universe_member_count=len(companies),
            company_count=0,
            candle_version_count=0,
            provenance_status=ResearchDatasetProvenanceStatus.UNKNOWN.value,
            value_reproducible=False,
            git_revision=git_revision.head,
            git_dirty=git_revision.dirty,
            notes=notes,
        )
        await self.repository.create_snapshot(snapshot)
        members = [
            self._member(
                snapshot.id,
                company,
                role=ResearchDatasetMemberRole.UNIVERSE,
                source=membership_source,
            )
            for company in companies
        ]
        members.append(
            self._member(
                snapshot.id,
                benchmark_company,
                role=ResearchDatasetMemberRole.BENCHMARK,
                source="EXPLICIT_BENCHMARK",
            )
        )
        await self.repository.add_universe_members(members)
        await self.repository.freeze_latest_versions(snapshot)
        dataset_hash = await self._dataset_hash(snapshot.id)
        (
            candle_count,
            company_count,
            minimum_day,
            maximum_day,
            provenance,
        ) = await self.repository.snapshot_statistics(snapshot.id)
        snapshot.company_count = company_count
        snapshot.candle_version_count = candle_count
        snapshot.minimum_trading_day = minimum_day
        snapshot.maximum_trading_day = maximum_day
        snapshot.universe_sha256 = hash_universe(company.ticker for company in companies)
        snapshot.dataset_sha256 = dataset_hash
        snapshot.provenance_status = provenance
        snapshot.value_reproducible = True
        snapshot.finalized_at = datetime.now(UTC)
        snapshot.creation_duration_ms = round((time.perf_counter() - started) * 1000)
        await self.repository.finalize(snapshot)
        return ResearchDatasetManifestSchema.model_validate(snapshot)

    async def get_manifest(self, snapshot_id: UUID) -> ResearchDatasetManifestSchema:
        snapshot = await self._finalized(snapshot_id)
        return ResearchDatasetManifestSchema.model_validate(snapshot)

    async def list_manifests(self) -> list[ResearchDatasetManifestSchema]:
        return [
            ResearchDatasetManifestSchema.model_validate(snapshot)
            for snapshot in await self.repository.list_snapshots()
        ]

    async def verify(self, snapshot_id: UUID) -> ResearchDatasetVerificationSchema:
        started = time.perf_counter()
        snapshot = await self._finalized(snapshot_id)
        members = await self.repository.list_members(
            snapshot_id, role=ResearchDatasetMemberRole.UNIVERSE
        )
        universe_hash = hash_universe(member.ticker_at_snapshot for member in members)
        dataset_hash = await self._dataset_hash(snapshot_id)
        candle_count, _, _, _, _ = await self.repository.snapshot_statistics(snapshot_id)
        errors: list[str] = []
        if dataset_hash != snapshot.dataset_sha256:
            errors.append("dataset SHA-256 mismatch")
        if universe_hash != snapshot.universe_sha256:
            errors.append("universe SHA-256 mismatch")
        if candle_count != snapshot.candle_version_count:
            errors.append("candle row count mismatch")
        if len(members) != snapshot.universe_member_count:
            errors.append("universe member count mismatch")
        if errors:
            raise ResearchDatasetVerificationError("; ".join(errors))
        return ResearchDatasetVerificationSchema(
            snapshot_id=snapshot_id,
            verified=True,
            dataset_sha256=dataset_hash,
            universe_sha256=universe_hash,
            candle_rows=candle_count,
            universe_members=len(members),
            duration_ms=round((time.perf_counter() - started) * 1000),
        )

    async def load_snapshot_dataset(self, snapshot_id: UUID) -> dict[str, list[DailyCandle]]:
        await self._finalized(snapshot_id)
        members = await self.repository.list_members(snapshot_id)
        snapshot = await self.repository.get(snapshot_id)
        assert snapshot is not None
        return {
            member.ticker_at_snapshot: list(
                await self.repository.get_frozen_history(
                    snapshot_id,
                    member.company_id,
                    snapshot.requested_start,
                    snapshot.requested_end,
                )
            )
            for member in members
        }

    async def _dataset_hash(self, snapshot_id: UUID) -> str:
        digest = hashlib.sha256()
        async for row in self.repository.stream_canonical_rows(snapshot_id):
            digest.update(canonical_candle_line(row))
        return digest.hexdigest()

    async def _finalized(self, snapshot_id: UUID) -> ResearchDatasetSnapshot:
        snapshot = await self.repository.get(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Research dataset {snapshot_id} not found")
        if snapshot.status != ResearchDatasetStatus.FINALIZED.value:
            raise ValueError("Research dataset is not finalized")
        return snapshot

    @staticmethod
    def _member(
        snapshot_id: UUID,
        company: Company,
        *,
        role: ResearchDatasetMemberRole,
        source: str,
    ) -> ResearchDatasetUniverseMember:
        return ResearchDatasetUniverseMember(
            snapshot_id=snapshot_id,
            company_id=company.id,
            role=role.value,
            ticker_at_snapshot=company.ticker.strip().upper(),
            company_name_at_snapshot=company.name,
            exchange_at_snapshot=company.exchange,
            sector_at_snapshot=company.sector,
            membership_source=source,
        )
