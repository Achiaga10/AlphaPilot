from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from alphapilot.database.models.company import Company
from alphapilot.market.dto import CompanyMetadata
from alphapilot.schemas.company import CompanyUpdate
from alphapilot.services.custom_ticker import CustomTickerService, CustomTickerState
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketTickerSyncResult,
)


class Companies:
    def __init__(self) -> None:
        self.items: dict[str, Company] = {}
        self.created = 0

    async def get_company(self, ticker: str) -> Company | None:
        return self.items.get(ticker.upper())

    async def create(self, company: Company) -> Company:
        company.id = uuid4()
        self.items[company.ticker] = company
        self.created += 1
        return company

    async def update_company(self, company_id: object, data: CompanyUpdate) -> Company | None:
        company = next(item for item in self.items.values() if item.id == company_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(company, field, value)
        return company


class Memberships:
    def __init__(self, members: set[str] | None = None) -> None:
        self.members = members or set()

    async def is_active_member(self, index_symbol: str, ticker: str) -> bool:
        assert index_symbol == "^GSPC"
        return ticker in self.members


class Metadata:
    def __init__(self, value: CompanyMetadata | None) -> None:
        self.value = value
        self.calls: list[str] = []

    async def get_company_metadata(self, ticker: str) -> CompanyMetadata | None:
        self.calls.append(ticker)
        return self.value


class Sync:
    def __init__(self, failure: MarketBatchSyncFailure | None = None) -> None:
        self.failure = failure
        self.calls: list[str] = []

    async def sync_ticker(self, ticker: str, start: date, end: date) -> MarketTickerSyncResult:
        self.calls.append(ticker)
        return MarketTickerSyncResult(
            ticker=ticker,
            synced=self.failure is None,
            skipped=False,
            failure=self.failure,
        )


class Candles:
    async def company_candle_summary(self, ticker: str) -> tuple[int, date | None, date | None]:
        return 280, date(2025, 7, 1), date(2026, 8, 25)


def service(
    companies: Companies,
    memberships: Memberships | None = None,
    metadata: Metadata | None = None,
    sync: Sync | None = None,
) -> CustomTickerService:
    return CustomTickerService(
        companies,
        memberships or Memberships(),
        metadata
        or Metadata(
            CompanyMetadata(
                ticker="SBET",
                name="SharpLink Gaming",
                exchange="NASDAQ",
                sector=None,
                industry=None,
                market_cap=Decimal("1000000"),
            )
        ),
        sync or Sync(),
        Candles(),
    )


@pytest.mark.asyncio
async def test_new_non_sp500_ticker_is_created_tracked_and_synced() -> None:
    companies = Companies()
    result = await service(companies).add_and_sync(" sbet ", date(2025, 7, 1), date(2026, 8, 25))
    assert result.state == CustomTickerState.TRACKED_AND_SYNCED
    assert result.ticker == "SBET"
    assert result.is_custom_tracked is True
    assert result.is_sp500_member is False
    assert result.sector is None
    assert result.stored_candle_count == 280
    assert companies.created == 1


@pytest.mark.asyncio
async def test_deactivate_preserves_company_and_readd_reactivates_without_duplicate() -> None:
    companies = Companies()
    tracker = service(companies)
    await tracker.add_and_sync("SBET", date(2025, 7, 1), date(2026, 8, 25))
    deactivated = await tracker.deactivate("SBET")
    assert deactivated.state == CustomTickerState.DEACTIVATED
    assert deactivated.is_custom_tracked is False
    assert deactivated.stored_candle_count == 280
    reactivated = await tracker.add_and_sync("SBET", date(2025, 7, 1), date(2026, 8, 25))
    assert reactivated.state == CustomTickerState.REACTIVATED_AND_SYNCED
    assert companies.created == 1


@pytest.mark.asyncio
async def test_sp500_ticker_is_not_duplicated_or_marked_custom() -> None:
    companies = Companies()
    aapl = Company(
        id=uuid4(),
        ticker="AAPL",
        name="Apple",
        exchange="NASDAQ",
        is_active=True,
        is_custom_tracked=False,
    )
    companies.items["AAPL"] = aapl
    result = await service(companies, Memberships({"AAPL"})).add_and_sync(
        "AAPL", date(2025, 7, 1), date(2026, 8, 25)
    )
    assert result.state == CustomTickerState.ALREADY_SP500
    assert result.is_custom_tracked is False
    assert companies.created == 0


@pytest.mark.asyncio
async def test_unknown_symbol_and_metadata_failure_do_not_persist_company() -> None:
    companies = Companies()
    missing = await service(companies, metadata=Metadata(None)).add_and_sync(
        "FAKE", date(2025, 7, 1), date(2026, 8, 25)
    )
    assert missing.state == CustomTickerState.SYMBOL_NOT_FOUND
    assert companies.items == {}

    class FailedMetadata(Metadata):
        async def get_company_metadata(self, ticker: str) -> CompanyMetadata | None:
            raise httpx.ConnectError("provider unavailable")

    failed = await service(companies, metadata=FailedMetadata(None)).add_and_sync(
        "SBET", date(2025, 7, 1), date(2026, 8, 25)
    )
    assert failed.state == CustomTickerState.METADATA_PROVIDER_FAILED
    assert companies.items == {}


@pytest.mark.asyncio
async def test_candle_failure_is_typed_partial_onboarding() -> None:
    companies = Companies()
    failed_sync = Sync(
        MarketBatchSyncFailure(
            ticker="SBET",
            error="Alpaca feed is not authorized.",
            code="MARKET_DATA_FEED_NOT_AUTHORIZED",
            provider="Alpaca",
            feed="sip",
        )
    )
    result = await service(companies, sync=failed_sync).add_and_sync(
        "SBET", date(2025, 7, 1), date(2026, 8, 25)
    )
    assert result.state == CustomTickerState.TRACKED_CANDLE_SYNC_FAILED
    assert result.is_custom_tracked is True
    assert "authorized" in result.message
