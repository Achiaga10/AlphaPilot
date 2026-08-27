from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

import httpx

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.database.models.market_data_ingestion import CandleProvenanceStatus
from alphapilot.market.dto.candle import MarketCandle
from alphapilot.market.provenance import CandleUpsertResult, CandleVersionProvenance
from alphapilot.market.providers.errors import MarketDataProviderError
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketBatchSyncResult,
    MarketTickerSyncResult,
)
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService


class BulkHistoricalMarketProvider(Protocol):
    async def get_history_many(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[MarketCandle]]:
        """Return historical candles for multiple tickers."""


class UniverseRepository(Protocol):
    async def list_active(
        self,
        index_symbol: str,
    ) -> list[IndexConstituent]:
        """Return active constituents for an index."""


class CompanyLookupService(Protocol):
    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        """Return one company by ticker."""

    async def list_companies(
        self,
    ) -> list[Company]:
        """Return all companies."""


class CandleUpsertService(Protocol):
    async def upsert_many(
        self,
        candles: list[DailyCandle],
        *,
        provenance: CandleVersionProvenance | None = None,
    ) -> CandleUpsertResult:
        """Upsert daily candles."""


class AlpacaBulkMarketSyncService:
    """Synchronizes market history using Alpaca bulk requests."""

    def __init__(
        self,
        provider: BulkHistoricalMarketProvider,
        universe_repository: UniverseRepository,
        company_service: CompanyLookupService,
        candle_service: CandleUpsertService,
        ingestion_batch_service: MarketDataIngestionBatchService,
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.universe_repository = universe_repository
        self.company_service = company_service
        self.candle_service = candle_service
        self.ingestion_batch_service = ingestion_batch_service
        self.session_policy = session_policy or CompletedDailySessionPolicy()

    async def sync_ticker(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> MarketTickerSyncResult:
        self._validate_date_range(
            start=start,
            end=end,
        )

        normalized_ticker = ticker.strip().upper()

        result = await self.sync_tickers([normalized_ticker], start, end)
        failure = result.failures[0] if result.failures else None
        return MarketTickerSyncResult(
            ticker=normalized_ticker,
            synced=result.synced == 1,
            skipped=result.skipped == 1,
            failure=failure,
            ingestion_batch_id=result.ingestion_batch_id,
        )

    async def sync_tickers(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> MarketBatchSyncResult:
        """Synchronize an explicit ticker group with one Alpaca bulk request."""
        self._validate_date_range(start=start, end=end)
        normalized = sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})
        companies = await self.company_service.list_companies()
        companies_by_ticker = {company.ticker.strip().upper(): company for company in companies}
        available = [ticker for ticker in normalized if ticker in companies_by_ticker]
        skipped = len(normalized) - len(available)
        if not available:
            return MarketBatchSyncResult(len(normalized), len(normalized), 0, skipped, (), None)
        provider_name = "alpaca"
        feed = self._provider_feed()
        ingestion_batch = await self.ingestion_batch_service.start(
            provider=provider_name,
            feed=feed,
            timeframe="1Day",
            adjustment="split",
            requested_start=start,
            requested_end=end,
            symbols_requested=len(available),
            benchmark_ticker=("SPY" if "SPY" in available else None),
            request_metadata={"sort": "asc"},
        )
        try:
            market_data = await self.provider.get_history_many(available, start, end)
        except MarketDataProviderError as exc:
            await self.ingestion_batch_service.fail(ingestion_batch, failed=len(available))
            failure = exc.failure
            return MarketBatchSyncResult(
                len(normalized),
                len(normalized),
                0,
                skipped,
                tuple(
                    MarketBatchSyncFailure(
                        ticker=ticker,
                        error=failure.message,
                        code=failure.code,
                        provider=failure.provider,
                        feed=failure.feed,
                    )
                    for ticker in available
                ),
                None,
                ingestion_batch.id,
            )
        except httpx.HTTPError:
            await self.ingestion_batch_service.fail(ingestion_batch, failed=len(available))
            return MarketBatchSyncResult(
                len(normalized),
                len(normalized),
                0,
                skipped,
                tuple(
                    MarketBatchSyncFailure(
                        ticker=ticker,
                        error="Alpaca market-data request failed.",
                        provider="Alpaca",
                    )
                    for ticker in available
                ),
                None,
                ingestion_batch.id,
            )
        try:
            candles_to_upsert: list[DailyCandle] = []
            synced = 0
            for ticker in available:
                candles = [
                    candle
                    for candle in market_data.get(ticker, [])
                    if self.session_policy.is_complete(candle.date)
                ]
                if not candles:
                    skipped += 1
                    continue
                candles_to_upsert.extend(
                    self._build_daily_candles(companies_by_ticker[ticker].id, candles)
                )
                synced += 1
            if candles_to_upsert:
                await self.candle_service.upsert_many(
                    candles_to_upsert,
                    provenance=CandleVersionProvenance(
                        provider=provider_name,
                        feed=feed,
                        ingestion_batch_id=ingestion_batch.id,
                        observed_at=datetime.now(UTC),
                        status=CandleProvenanceStatus.COMPLETE,
                    ),
                )
            await self.ingestion_batch_service.complete(ingestion_batch, succeeded=synced, failed=0)
        except Exception:
            await self.ingestion_batch_service.fail_after_error(
                ingestion_batch.id,
                succeeded=synced,
                failed=len(available) - synced,
            )
            raise
        return MarketBatchSyncResult(
            len(normalized),
            len(normalized),
            synced,
            skipped,
            (),
            None,
            ingestion_batch.id,
        )

    async def sync_batch(
        self,
        index_symbol: str,
        start: date,
        end: date,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> MarketBatchSyncResult:
        self._validate_date_range(
            start=start,
            end=end,
        )

        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        constituents = await self.universe_repository.list_active(index_symbol)

        total_active = len(constituents)

        batch = constituents[offset : offset + limit]

        if not batch:
            return MarketBatchSyncResult(
                total_active=total_active,
                attempted=0,
                synced=0,
                skipped=0,
                failures=(),
                next_offset=None,
            )

        batch_tickers = [constituent.ticker.strip().upper() for constituent in batch]
        explicit = await self.sync_tickers(batch_tickers, start, end)

        return self._build_batch_result(
            total_active=total_active,
            batch_size=len(batch),
            offset=offset,
            synced=explicit.synced,
            skipped=explicit.skipped,
            failures=list(explicit.failures),
            ingestion_batch_id=explicit.ingestion_batch_id,
        )

    @staticmethod
    def _build_daily_candles(
        company_id: UUID,
        market_candles: list[MarketCandle],
    ) -> list[DailyCandle]:
        return [
            DailyCandle(
                company_id=company_id,
                trading_day=candle.date,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
            for candle in market_candles
        ]

    @staticmethod
    def _build_batch_result(
        *,
        total_active: int,
        batch_size: int,
        offset: int,
        synced: int,
        skipped: int,
        failures: list[MarketBatchSyncFailure],
        ingestion_batch_id: UUID | None,
    ) -> MarketBatchSyncResult:
        processed_until = offset + batch_size

        next_offset = processed_until if processed_until < total_active else None

        return MarketBatchSyncResult(
            total_active=total_active,
            attempted=batch_size,
            synced=synced,
            skipped=skipped,
            failures=tuple(failures),
            next_offset=next_offset,
            ingestion_batch_id=ingestion_batch_id,
        )

    def _provider_feed(self) -> str:
        feed = getattr(self.provider, "feed", None)
        value = getattr(feed, "value", feed)
        return str(value).strip().lower() if value else "unknown"

    @staticmethod
    def _validate_date_range(
        *,
        start: date,
        end: date,
    ) -> None:
        if start > end:
            raise ValueError("start must be before or equal to end")
