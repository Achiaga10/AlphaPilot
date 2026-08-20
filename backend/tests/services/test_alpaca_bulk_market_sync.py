from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import (
    IndexConstituent,
)
from alphapilot.market.dto.candle import MarketCandle
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

    async def upsert_many(
        self,
        candles: list[DailyCandle],
    ) -> None:
        self.upsert_calls.append(candles)


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
