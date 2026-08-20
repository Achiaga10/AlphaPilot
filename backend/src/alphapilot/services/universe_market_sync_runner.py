from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from alphapilot.database.models.company import Company
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketBatchSyncResult,
    MarketTickerSyncResult,
)


class BatchMarketSync(Protocol):
    async def sync_batch(
        self,
        index_symbol: str,
        start: date,
        end: date,
        *,
        offset: int = 0,
        limit: int = 5,
    ) -> MarketBatchSyncResult:
        """Synchronize one universe batch."""

    async def sync_ticker(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> MarketTickerSyncResult:
        """Synchronize one ticker."""


class BenchmarkCompanyService(Protocol):
    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        """Return a company by ticker."""

    async def create(
        self,
        company: Company,
    ) -> Company:
        """Create a company."""


ProgressCallback = Callable[
    [MarketBatchSyncResult],
    None,
]


@dataclass(slots=True, frozen=True)
class UniverseMarketSyncSummary:
    total_active: int
    attempted: int
    synced: int
    skipped: int
    failures: tuple[MarketBatchSyncFailure, ...]
    benchmark_synced: bool
    completed: bool


class UniverseMarketSyncRunner:
    """Runs market synchronization across an entire index universe."""

    MARKET_BENCHMARK_TICKER = "SPY"
    MARKET_BENCHMARK_LOOKBACK_DAYS = 400

    def __init__(
        self,
        batch_sync_service: BatchMarketSync,
        company_service: BenchmarkCompanyService,
        checkpoint_path: Path,
    ) -> None:
        self.batch_sync_service = batch_sync_service
        self.company_service = company_service
        self.checkpoint_path = checkpoint_path

    async def run(
        self,
        index_symbol: str,
        start: date,
        end: date,
        *,
        batch_size: int = 5,
        resume: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> UniverseMarketSyncSummary:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")

        if start > end:
            raise ValueError("start must be before or equal to end")

        await self._ensure_benchmark_company()

        await self._sync_benchmark(
            end=end,
        )

        if resume:
            offset = self._load_checkpoint(
                index_symbol=index_symbol,
                start=start,
                end=end,
            )
        else:
            offset = 0
            self._clear_checkpoint()

        total_active = 0
        attempted = 0
        synced = 0
        skipped = 0

        failures: list[MarketBatchSyncFailure] = []

        while True:
            result = await self.batch_sync_service.sync_batch(
                index_symbol=index_symbol,
                start=start,
                end=end,
                offset=offset,
                limit=batch_size,
            )

            total_active = result.total_active

            attempted += result.attempted
            synced += result.synced
            skipped += result.skipped

            failures.extend(result.failures)

            if progress_callback is not None:
                progress_callback(result)

            if result.next_offset is None:
                self._clear_checkpoint()

                return UniverseMarketSyncSummary(
                    total_active=total_active,
                    attempted=attempted,
                    synced=synced,
                    skipped=skipped,
                    failures=tuple(failures),
                    benchmark_synced=True,
                    completed=True,
                )

            self._save_checkpoint(
                index_symbol=index_symbol,
                start=start,
                end=end,
                next_offset=result.next_offset,
            )

            offset = result.next_offset

    async def _ensure_benchmark_company(
        self,
    ) -> None:
        company = await self.company_service.get_company(
            self.MARKET_BENCHMARK_TICKER,
        )

        if company is not None:
            return

        await self.company_service.create(
            Company(
                ticker=self.MARKET_BENCHMARK_TICKER,
                name="SPY Benchmark",
                exchange="NYSEARCA",
                sector="ETF",
                industry="S&P 500 Benchmark",
                is_active=True,
            )
        )

    async def _sync_benchmark(
        self,
        end: date,
    ) -> None:
        start = end - timedelta(
            days=self.MARKET_BENCHMARK_LOOKBACK_DAYS,
        )

        result = await self.batch_sync_service.sync_ticker(
            ticker=self.MARKET_BENCHMARK_TICKER,
            start=start,
            end=end,
        )

        if result.failure is not None:
            raise RuntimeError(f"Failed to synchronize SPY benchmark: {result.failure.error}")

        if result.skipped:
            raise RuntimeError("SPY benchmark synchronization was skipped")

    def _load_checkpoint(
        self,
        *,
        index_symbol: str,
        start: date,
        end: date,
    ) -> int:
        if not self.checkpoint_path.exists():
            return 0

        try:
            payload = json.loads(
                self.checkpoint_path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError("Unable to read market sync checkpoint") from exc

        expected = {
            "index_symbol": index_symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

        actual = {
            "index_symbol": payload.get("index_symbol"),
            "start": payload.get("start"),
            "end": payload.get("end"),
        }

        if actual != expected:
            raise RuntimeError(
                "Existing market sync checkpoint "
                "belongs to a different sync range. "
                "Run again with resume disabled."
            )

        next_offset = payload.get("next_offset")

        if (
            not isinstance(
                next_offset,
                int,
            )
            or next_offset < 0
        ):
            raise RuntimeError("Invalid market sync checkpoint")

        return next_offset

    def _save_checkpoint(
        self,
        *,
        index_symbol: str,
        start: date,
        end: date,
        next_offset: int,
    ) -> None:
        self.checkpoint_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "index_symbol": index_symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "next_offset": next_offset,
        }

        self.checkpoint_path.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _clear_checkpoint(
        self,
    ) -> None:
        self.checkpoint_path.unlink(
            missing_ok=True,
        )
