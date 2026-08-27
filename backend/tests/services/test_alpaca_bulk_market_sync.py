from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import (
    IndexConstituent,
)
from alphapilot.database.models.market_data_ingestion import (
    IngestionBatchStatus,
    MarketDataIngestionBatch,
)
from alphapilot.market.dto.candle import MarketCandle
from alphapilot.market.provenance import CandleUpsertResult, CandleVersionProvenance
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.services.alpaca_bulk_market_sync import (
    AlpacaBulkMarketSyncService,
)


class FakeBulkProvider:
    def __init__(
        self,
        data: dict[str, list[MarketCandle]],
    ) -> None:
        self.data = data

        self.calls: list[
            tuple[
                list[str],
                date,
                date,
            ]
        ] = []

    async def get_history_many(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[MarketCandle]]:
        self.calls.append(
            (
                tickers,
                start,
                end,
            )
        )

        return {
            ticker: self.data.get(
                ticker,
                [],
            )
            for ticker in tickers
        }


class FailingBulkProvider:
    async def get_history_many(
        self,
        tickers: list[str],
        start: date,
        end: date,
    ) -> dict[str, list[MarketCandle]]:
        request = httpx.Request(
            "GET",
            "https://data.alpaca.markets/v2/stocks/bars",
        )

        response = httpx.Response(
            status_code=500,
            request=request,
        )

        raise httpx.HTTPStatusError(
            "Alpaca unavailable",
            request=request,
            response=response,
        )


class FakeUniverseRepository:
    def __init__(
        self,
        tickers: list[str],
    ) -> None:
        self.constituents = [
            IndexConstituent(
                id=uuid4(),
                index_symbol="^GSPC",
                ticker=ticker,
                is_active=True,
            )
            for ticker in tickers
        ]

    async def list_active(
        self,
        index_symbol: str,
    ) -> list[IndexConstituent]:
        assert index_symbol == "^GSPC"

        return self.constituents


class FakeCompanyService:
    def __init__(
        self,
        companies: list[Company],
    ) -> None:
        self.companies = companies

    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        normalized_ticker = ticker.upper()

        return next(
            (company for company in self.companies if company.ticker.upper() == normalized_ticker),
            None,
        )

    async def list_companies(
        self,
    ) -> list[Company]:
        return self.companies


class FakeCandleService:
    def __init__(self) -> None:
        self.upsert_calls: list[list[DailyCandle]] = []
        self.provenance_calls: list[CandleVersionProvenance] = []

    async def upsert_many(
        self,
        candles: list[DailyCandle],
        *,
        provenance: CandleVersionProvenance | None = None,
    ) -> CandleUpsertResult:
        self.upsert_calls.append(candles)
        assert provenance is not None
        self.provenance_calls.append(provenance)
        return CandleUpsertResult(len(candles), len(candles), len(candles), 0)


class FailingCandleService(FakeCandleService):
    async def upsert_many(
        self,
        candles: list[DailyCandle],
        *,
        provenance: CandleVersionProvenance | None = None,
    ) -> CandleUpsertResult:
        del candles, provenance
        raise RuntimeError("controlled candle write failure")


class FakeIngestionBatchService:
    def __init__(self) -> None:
        self.batches: list[MarketDataIngestionBatch] = []

    async def start(self, **kwargs: object) -> MarketDataIngestionBatch:
        batch = MarketDataIngestionBatch(
            id=uuid4(),
            provider=str(kwargs["provider"]),
            feed=str(kwargs["feed"]),
            timeframe=str(kwargs["timeframe"]),
            adjustment=str(kwargs["adjustment"]),
            requested_start=kwargs["requested_start"],
            requested_end=kwargs["requested_end"],
            benchmark_ticker=kwargs.get("benchmark_ticker"),
            request_metadata=kwargs.get("request_metadata", {}),
            symbols_requested=int(kwargs["symbols_requested"]),
            symbols_succeeded=0,
            symbols_failed=0,
            status=IngestionBatchStatus.RUNNING.value,
            created_at=datetime.now(UTC),
        )
        self.batches.append(batch)
        return batch

    async def complete(
        self, batch: MarketDataIngestionBatch, *, succeeded: int, failed: int
    ) -> MarketDataIngestionBatch:
        batch.status = IngestionBatchStatus.COMPLETED.value
        batch.symbols_succeeded = succeeded
        batch.symbols_failed = failed
        return batch

    async def fail(
        self, batch: MarketDataIngestionBatch, *, succeeded: int = 0, failed: int
    ) -> MarketDataIngestionBatch:
        batch.status = IngestionBatchStatus.FAILED.value
        batch.symbols_succeeded = succeeded
        batch.symbols_failed = failed
        return batch

    async def fail_after_error(
        self, batch_id: object, *, succeeded: int = 0, failed: int
    ) -> MarketDataIngestionBatch:
        batch = next(item for item in self.batches if item.id == batch_id)
        return await self.fail(batch, succeeded=succeeded, failed=failed)


def create_company(
    ticker: str,
) -> Company:
    return Company(
        id=uuid4(),
        ticker=ticker,
        name=f"{ticker} Company",
        exchange="NASDAQ",
        sector="Technology",
        industry="Software",
        is_active=True,
    )


def create_market_candle(
    trading_day: date,
    close: str,
) -> MarketCandle:
    close_decimal = Decimal(close)

    return MarketCandle(
        date=trading_day,
        open=close_decimal,
        high=close_decimal + Decimal("1"),
        low=close_decimal - Decimal("1"),
        close=close_decimal,
        volume=100000,
    )


@pytest.mark.asyncio
async def test_sync_batch_uses_single_bulk_request() -> None:
    aapl = create_company("AAPL")

    msft = create_company("MSFT")

    provider = FakeBulkProvider(
        {
            "AAPL": [
                create_market_candle(
                    date(2026, 8, 17),
                    "200",
                ),
                create_market_candle(
                    date(2026, 8, 18),
                    "201",
                ),
            ],
            "MSFT": [
                create_market_candle(
                    date(2026, 8, 17),
                    "500",
                ),
            ],
        }
    )

    candle_service = FakeCandleService()

    service = AlpacaBulkMarketSyncService(
        provider=provider,
        universe_repository=(
            FakeUniverseRepository(
                [
                    "AAPL",
                    "MSFT",
                    "MISSING",
                ]
            )
        ),
        company_service=(
            FakeCompanyService(
                [
                    aapl,
                    msft,
                ]
            )
        ),
        candle_service=candle_service,
        ingestion_batch_service=FakeIngestionBatchService(),
    )

    result = await service.sync_batch(
        index_symbol="^GSPC",
        start=date(2026, 8, 17),
        end=date(2026, 8, 18),
        offset=0,
        limit=100,
    )

    assert result.total_active == 3
    assert result.attempted == 3
    assert result.synced == 2
    assert result.skipped == 1
    assert result.failures == ()
    assert result.next_offset is None

    assert len(provider.calls) == 1

    tickers, start, end = provider.calls[0]

    assert tickers == [
        "AAPL",
        "MSFT",
    ]

    assert start == date(
        2026,
        8,
        17,
    )

    assert end == date(
        2026,
        8,
        18,
    )

    assert len(candle_service.upsert_calls) == 1

    candles = candle_service.upsert_calls[0]

    assert len(candles) == 3

    aapl_candles = [candle for candle in candles if candle.company_id == aapl.id]

    msft_candles = [candle for candle in candles if candle.company_id == msft.id]

    assert len(aapl_candles) == 2

    assert len(msft_candles) == 1

    assert aapl_candles[0].close == Decimal("200")

    assert aapl_candles[1].close == Decimal("201")

    assert msft_candles[0].close == Decimal("500")


@pytest.mark.asyncio
async def test_sync_ticker_supports_spy() -> None:
    spy = create_company("SPY")

    provider = FakeBulkProvider(
        {
            "SPY": [
                create_market_candle(
                    date(2026, 8, 18),
                    "650",
                )
            ]
        }
    )

    candle_service = FakeCandleService()

    service = AlpacaBulkMarketSyncService(
        provider=provider,
        universe_repository=(FakeUniverseRepository([])),
        company_service=(FakeCompanyService([spy])),
        candle_service=candle_service,
        ingestion_batch_service=FakeIngestionBatchService(),
    )

    result = await service.sync_ticker(
        ticker="SPY",
        start=date(2025, 7, 15),
        end=date(2026, 8, 18),
    )

    assert result.synced is True
    assert result.skipped is False
    assert result.failure is None

    assert len(provider.calls) == 1

    assert provider.calls[0][0] == ["SPY"]

    assert len(candle_service.upsert_calls) == 1

    candles = candle_service.upsert_calls[0]

    assert len(candles) == 1

    assert candles[0].company_id == spy.id

    assert candles[0].close == Decimal("650")
    assert candle_service.provenance_calls[0].provider == "alpaca"
    assert candle_service.provenance_calls[0].feed == "unknown"
    assert candle_service.provenance_calls[0].ingestion_batch_id == result.ingestion_batch_id


@pytest.mark.asyncio
async def test_sync_batch_records_provider_failure() -> None:
    aapl = create_company("AAPL")

    msft = create_company("MSFT")

    candle_service = FakeCandleService()

    service = AlpacaBulkMarketSyncService(
        provider=FailingBulkProvider(),
        universe_repository=(
            FakeUniverseRepository(
                [
                    "AAPL",
                    "MSFT",
                ]
            )
        ),
        company_service=(
            FakeCompanyService(
                [
                    aapl,
                    msft,
                ]
            )
        ),
        candle_service=candle_service,
        ingestion_batch_service=FakeIngestionBatchService(),
    )

    result = await service.sync_batch(
        index_symbol="^GSPC",
        start=date(2026, 8, 17),
        end=date(2026, 8, 18),
        limit=100,
    )

    assert result.attempted == 2
    assert result.synced == 0
    assert result.skipped == 0

    assert len(result.failures) == 2

    assert {failure.ticker for failure in result.failures} == {
        "AAPL",
        "MSFT",
    }

    assert candle_service.upsert_calls == []


@pytest.mark.asyncio
async def test_sync_batch_respects_offset_and_limit() -> None:
    companies = [
        create_company(ticker)
        for ticker in [
            "AAPL",
            "MSFT",
            "NVDA",
        ]
    ]

    provider = FakeBulkProvider(
        {
            "MSFT": [
                create_market_candle(
                    date(2026, 8, 18),
                    "500",
                )
            ]
        }
    )

    service = AlpacaBulkMarketSyncService(
        provider=provider,
        universe_repository=(
            FakeUniverseRepository(
                [
                    "AAPL",
                    "MSFT",
                    "NVDA",
                ]
            )
        ),
        company_service=(FakeCompanyService(companies)),
        candle_service=(FakeCandleService()),
        ingestion_batch_service=FakeIngestionBatchService(),
    )

    result = await service.sync_batch(
        index_symbol="^GSPC",
        start=date(2026, 8, 17),
        end=date(2026, 8, 18),
        offset=1,
        limit=1,
    )

    assert result.total_active == 3
    assert result.attempted == 1
    assert result.synced == 1
    assert result.next_offset == 2

    assert provider.calls[0][0] == ["MSFT"]


@pytest.mark.asyncio
async def test_bulk_sync_excludes_provider_current_session_partial_bar() -> None:
    spy = create_company("SPY")
    provider = FakeBulkProvider(
        {
            "SPY": [
                create_market_candle(date(2026, 8, 25), "760"),
                create_market_candle(date(2026, 8, 26), "999"),
            ]
        }
    )
    candles = FakeCandleService()
    policy = CompletedDailySessionPolicy(
        now_provider=lambda: datetime(2026, 8, 26, 18, 0, tzinfo=UTC)
    )
    service = AlpacaBulkMarketSyncService(
        provider=provider,
        universe_repository=FakeUniverseRepository([]),
        company_service=FakeCompanyService([spy]),
        candle_service=candles,
        ingestion_batch_service=FakeIngestionBatchService(),
        session_policy=policy,
    )

    result = await service.sync_ticker(ticker="SPY", start=date(2026, 8, 25), end=date(2026, 8, 26))

    assert result.synced is True
    assert len(candles.upsert_calls) == 1
    assert [item.trading_day for item in candles.upsert_calls[0]] == [date(2026, 8, 25)]


@pytest.mark.asyncio
async def test_candle_write_failure_marks_ingestion_batch_failed() -> None:
    service_batches = FakeIngestionBatchService()
    service = AlpacaBulkMarketSyncService(
        provider=FakeBulkProvider({"AAPL": [create_market_candle(date(2026, 8, 18), "200")]}),
        universe_repository=FakeUniverseRepository([]),
        company_service=FakeCompanyService([create_company("AAPL")]),
        candle_service=FailingCandleService(),
        ingestion_batch_service=service_batches,
    )

    with pytest.raises(RuntimeError, match="controlled candle write failure"):
        await service.sync_ticker("AAPL", date(2026, 8, 18), date(2026, 8, 18))

    assert service_batches.batches[0].status == IngestionBatchStatus.FAILED.value
