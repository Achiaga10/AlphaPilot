from datetime import date
from pathlib import Path

import pytest

from alphapilot.database.models.company import Company
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketBatchSyncResult,
    MarketTickerSyncResult,
)
from alphapilot.services.universe_market_sync_runner import (
    UniverseMarketSyncRunner,
)


class FakeCompanyService:
    def __init__(self) -> None:
        self.companies: dict[str, Company] = {}

    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        return self.companies.get(ticker.upper())

    async def create(
        self,
        company: Company,
    ) -> Company:
        self.companies[company.ticker.upper()] = company

        return company


class FakeBatchSyncService:
    def __init__(
        self,
        results: list[MarketBatchSyncResult],
        *,
        fail_on_call: int | None = None,
    ) -> None:
        self.results = results
        self.fail_on_call = fail_on_call

        self.calls = 0

        self.offsets: list[int] = []
        self.synced_tickers: list[str] = []

    async def sync_ticker(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> MarketTickerSyncResult:
        self.synced_tickers.append(ticker)

        return MarketTickerSyncResult(
            ticker=ticker,
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
        limit: int = 5,
    ) -> MarketBatchSyncResult:
        self.calls += 1

        self.offsets.append(offset)

        if self.fail_on_call is not None and self.calls == self.fail_on_call:
            raise RuntimeError("Simulated interruption")

        return self.results.pop(0)


@pytest.mark.asyncio
async def test_runner_processes_all_batches(
    tmp_path: Path,
) -> None:
    first_batch = MarketBatchSyncResult(
        total_active=5,
        attempted=2,
        synced=2,
        skipped=0,
        failures=(),
        next_offset=2,
    )

    second_batch = MarketBatchSyncResult(
        total_active=5,
        attempted=3,
        synced=2,
        skipped=0,
        failures=(
            MarketBatchSyncFailure(
                ticker="NVDA",
                error="Provider unavailable",
            ),
        ),
        next_offset=None,
    )

    batch_service = FakeBatchSyncService(
        [
            first_batch,
            second_batch,
        ]
    )

    company_service = FakeCompanyService()

    checkpoint = tmp_path / "checkpoint.json"

    runner = UniverseMarketSyncRunner(
        batch_sync_service=batch_service,
        company_service=company_service,
        checkpoint_path=checkpoint,
    )

    summary = await runner.run(
        index_symbol="^GSPC",
        start=date(2026, 4, 1),
        end=date(2026, 8, 19),
        batch_size=2,
    )

    assert summary.completed is True

    assert summary.benchmark_synced is True

    assert summary.total_active == 5
    assert summary.attempted == 5
    assert summary.synced == 4
    assert summary.skipped == 0

    assert len(summary.failures) == 1

    assert summary.failures[0].ticker == "NVDA"

    assert batch_service.offsets == [
        0,
        2,
    ]

    assert batch_service.synced_tickers == [
        "SPY",
    ]

    spy = await company_service.get_company("SPY")

    assert spy is not None
    assert spy.ticker == "SPY"
    assert spy.exchange == "NYSEARCA"
    assert spy.sector == "ETF"

    assert checkpoint.exists() is False


@pytest.mark.asyncio
async def test_runner_resumes_from_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.json"

    first_run_service = FakeBatchSyncService(
        [
            MarketBatchSyncResult(
                total_active=4,
                attempted=2,
                synced=2,
                skipped=0,
                failures=(),
                next_offset=2,
            ),
        ],
        fail_on_call=2,
    )

    first_company_service = FakeCompanyService()

    first_runner = UniverseMarketSyncRunner(
        batch_sync_service=first_run_service,
        company_service=first_company_service,
        checkpoint_path=checkpoint,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated interruption",
    ):
        await first_runner.run(
            index_symbol="^GSPC",
            start=date(2026, 4, 1),
            end=date(2026, 8, 19),
            batch_size=2,
        )

    assert checkpoint.exists() is True

    assert first_run_service.offsets == [
        0,
        2,
    ]

    assert first_run_service.synced_tickers == [
        "SPY",
    ]

    second_run_service = FakeBatchSyncService(
        [
            MarketBatchSyncResult(
                total_active=4,
                attempted=2,
                synced=2,
                skipped=0,
                failures=(),
                next_offset=None,
            )
        ]
    )

    second_company_service = FakeCompanyService()

    second_runner = UniverseMarketSyncRunner(
        batch_sync_service=second_run_service,
        company_service=second_company_service,
        checkpoint_path=checkpoint,
    )

    summary = await second_runner.run(
        index_symbol="^GSPC",
        start=date(2026, 4, 1),
        end=date(2026, 8, 19),
        batch_size=2,
    )

    assert summary.completed is True

    assert summary.benchmark_synced is True

    assert second_run_service.offsets == [
        2,
    ]

    assert second_run_service.synced_tickers == [
        "SPY",
    ]

    assert checkpoint.exists() is False


@pytest.mark.asyncio
async def test_runner_reuses_existing_benchmark_company(
    tmp_path: Path,
) -> None:
    batch_service = FakeBatchSyncService(
        [
            MarketBatchSyncResult(
                total_active=1,
                attempted=1,
                synced=1,
                skipped=0,
                failures=(),
                next_offset=None,
            )
        ]
    )

    company_service = FakeCompanyService()

    existing_spy = Company(
        ticker="SPY",
        name="SPDR S&P 500 ETF Trust",
        exchange="NYSEARCA",
        sector="ETF",
        industry="Index ETF",
        is_active=True,
    )

    await company_service.create(existing_spy)

    checkpoint = tmp_path / "checkpoint.json"

    runner = UniverseMarketSyncRunner(
        batch_sync_service=batch_service,
        company_service=company_service,
        checkpoint_path=checkpoint,
    )

    summary = await runner.run(
        index_symbol="^GSPC",
        start=date(2026, 4, 1),
        end=date(2026, 8, 19),
        batch_size=5,
    )

    assert summary.completed is True
    assert summary.benchmark_synced is True

    spy = await company_service.get_company("SPY")

    assert spy is existing_spy

    assert batch_service.synced_tickers == [
        "SPY",
    ]


@pytest.mark.asyncio
async def test_runner_stops_when_benchmark_sync_fails(
    tmp_path: Path,
) -> None:
    class FailingBenchmarkBatchService(
        FakeBatchSyncService,
    ):
        async def sync_ticker(
            self,
            ticker: str,
            start: date,
            end: date,
        ) -> MarketTickerSyncResult:
            self.synced_tickers.append(ticker)

            return MarketTickerSyncResult(
                ticker=ticker,
                synced=False,
                skipped=False,
                failure=MarketBatchSyncFailure(
                    ticker=ticker,
                    error="Polygon unavailable",
                ),
            )

    batch_service = FailingBenchmarkBatchService(
        [
            MarketBatchSyncResult(
                total_active=1,
                attempted=1,
                synced=1,
                skipped=0,
                failures=(),
                next_offset=None,
            )
        ]
    )

    company_service = FakeCompanyService()

    checkpoint = tmp_path / "checkpoint.json"

    runner = UniverseMarketSyncRunner(
        batch_sync_service=batch_service,
        company_service=company_service,
        checkpoint_path=checkpoint,
    )

    with pytest.raises(
        RuntimeError,
        match=("Failed to synchronize SPY benchmark"),
    ):
        await runner.run(
            index_symbol="^GSPC",
            start=date(2026, 4, 1),
            end=date(2026, 8, 19),
            batch_size=5,
        )

    assert batch_service.synced_tickers == [
        "SPY",
    ]

    # No universe batch should run if
    # the benchmark could not be synchronized.
    assert batch_service.offsets == []
