from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

import httpx

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.market.dto.candle import MarketCandle
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketBatchSyncResult,
    MarketTickerSyncResult,
)


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
    ) -> None:
        """Upsert daily candles."""


class AlpacaBulkMarketSyncService:
    """Synchronizes market history using Alpaca bulk requests."""

    def __init__(
        self,
        provider: BulkHistoricalMarketProvider,
        universe_repository: UniverseRepository,
        company_service: CompanyLookupService,
        candle_service: CandleUpsertService,
    ) -> None:
        self.provider = provider
        self.universe_repository = universe_repository
        self.company_service = company_service
        self.candle_service = candle_service

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

        company = await self.company_service.get_company(normalized_ticker)

        if company is None:
            return MarketTickerSyncResult(
                ticker=normalized_ticker,
                synced=False,
                skipped=True,
                failure=None,
            )

        try:
            market_data = await self.provider.get_history_many(
                tickers=[normalized_ticker],
                start=start,
                end=end,
            )
        except httpx.HTTPError as exc:
            return MarketTickerSyncResult(
                ticker=normalized_ticker,
                synced=False,
                skipped=False,
                failure=MarketBatchSyncFailure(
                    ticker=normalized_ticker,
                    error=str(exc),
                ),
            )

        market_candles = market_data.get(
            normalized_ticker,
            [],
        )

        if not market_candles:
            return MarketTickerSyncResult(
                ticker=normalized_ticker,
                synced=False,
                skipped=True,
                failure=None,
            )

        candles = self._build_daily_candles(
            company_id=company.id,
            market_candles=market_candles,
        )

        await self.candle_service.upsert_many(candles)

        return MarketTickerSyncResult(
            ticker=normalized_ticker,
            synced=True,
            skipped=False,
            failure=None,
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

        companies = await self.company_service.list_companies()

        companies_by_ticker = {company.ticker.strip().upper(): company for company in companies}

        batch_tickers = [constituent.ticker.strip().upper() for constituent in batch]

        available_tickers = [ticker for ticker in batch_tickers if ticker in companies_by_ticker]

        skipped = len(batch_tickers) - len(available_tickers)

        failures: list[MarketBatchSyncFailure] = []

        synced = 0

        if available_tickers:
            try:
                market_data = await self.provider.get_history_many(
                    tickers=available_tickers,
                    start=start,
                    end=end,
                )
            except httpx.HTTPError as exc:
                failures.extend(
                    MarketBatchSyncFailure(
                        ticker=ticker,
                        error=str(exc),
                    )
                    for ticker in available_tickers
                )

                return self._build_batch_result(
                    total_active=total_active,
                    batch_size=len(batch),
                    offset=offset,
                    synced=0,
                    skipped=skipped,
                    failures=failures,
                )

            candles_to_upsert: list[DailyCandle] = []

            for ticker in available_tickers:
                company = companies_by_ticker[ticker]

                market_candles = market_data.get(
                    ticker,
                    [],
                )

                if not market_candles:
                    skipped += 1
                    continue

                candles_to_upsert.extend(
                    self._build_daily_candles(
                        company_id=company.id,
                        market_candles=market_candles,
                    )
                )

                synced += 1

            if candles_to_upsert:
                await self.candle_service.upsert_many(candles_to_upsert)

        return self._build_batch_result(
            total_active=total_active,
            batch_size=len(batch),
            offset=offset,
            synced=synced,
            skipped=skipped,
            failures=failures,
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
        )

    @staticmethod
    def _validate_date_range(
        *,
        start: date,
        end: date,
    ) -> None:
        if start > end:
            raise ValueError("start must be before or equal to end")
