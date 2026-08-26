from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import httpx

from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)


class CompanyMarketSync(Protocol):
    async def sync_company(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> bool:
        """Synchronize market history for a company."""


@dataclass(slots=True, frozen=True)
class MarketBatchSyncFailure:
    ticker: str
    error: str
    code: str = "MARKET_DATA_PROVIDER_ERROR"
    provider: str | None = None
    feed: str | None = None


@dataclass(slots=True, frozen=True)
class MarketTickerSyncResult:
    ticker: str
    synced: bool
    skipped: bool
    failure: MarketBatchSyncFailure | None


@dataclass(slots=True, frozen=True)
class MarketBatchSyncResult:
    total_active: int
    attempted: int
    synced: int
    skipped: int
    failures: tuple[MarketBatchSyncFailure, ...]
    next_offset: int | None


class MarketBatchSyncService:
    """Synchronizes market history for active index constituents."""

    def __init__(
        self,
        universe_repository: IndexConstituentRepository,
        market_sync_service: CompanyMarketSync,
        requests_per_minute: int = 0,
    ) -> None:
        self.universe_repository = universe_repository
        self.market_sync_service = market_sync_service
        self.requests_per_minute = requests_per_minute

        self._last_request_started_at: float | None = None

    async def sync_ticker(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> MarketTickerSyncResult:
        await self._wait_for_rate_limit()

        try:
            was_synced = await self.market_sync_service.sync_company(
                ticker=ticker,
                start=start,
                end=end,
            )

        except httpx.HTTPError as exc:
            failure = MarketBatchSyncFailure(
                ticker=ticker,
                error=str(exc),
            )

            return MarketTickerSyncResult(
                ticker=ticker,
                synced=False,
                skipped=False,
                failure=failure,
            )

        if was_synced:
            return MarketTickerSyncResult(
                ticker=ticker,
                synced=True,
                skipped=False,
                failure=None,
            )

        return MarketTickerSyncResult(
            ticker=ticker,
            synced=False,
            skipped=True,
            failure=None,
        )

    async def sync_batch(
        self,
        index_symbol: str,
        start: date,
        end: date,
        *,
        offset: int = 0,
        limit: int = 5,
    ) -> MarketBatchSyncResult:
        if start > end:
            raise ValueError("start must be before or equal to end")

        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        constituents = await self.universe_repository.list_active(
            index_symbol,
        )

        total_active = len(constituents)

        batch = constituents[offset : offset + limit]

        synced = 0
        skipped = 0
        failures: list[MarketBatchSyncFailure] = []

        for constituent in batch:
            result = await self.sync_ticker(
                ticker=constituent.ticker,
                start=start,
                end=end,
            )

            if result.failure is not None:
                failures.append(result.failure)
                continue

            if result.synced:
                synced += 1
            elif result.skipped:
                skipped += 1

        processed_until = offset + len(batch)

        next_offset = processed_until if processed_until < total_active else None

        return MarketBatchSyncResult(
            total_active=total_active,
            attempted=len(batch),
            synced=synced,
            skipped=skipped,
            failures=tuple(failures),
            next_offset=next_offset,
        )

    async def _wait_for_rate_limit(
        self,
    ) -> None:
        request_interval = self._request_interval_seconds()

        if request_interval <= 0:
            return

        now = time.monotonic()

        if self._last_request_started_at is not None:
            elapsed = now - self._last_request_started_at

            remaining = request_interval - elapsed

            if remaining > 0:
                await asyncio.sleep(remaining)

        self._last_request_started_at = time.monotonic()

    def _request_interval_seconds(
        self,
    ) -> float:
        if self.requests_per_minute <= 0:
            return 0.0

        return 60.0 / self.requests_per_minute + 0.25
