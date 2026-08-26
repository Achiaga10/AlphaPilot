from datetime import date

import pytest

from alphapilot.services.admin_data import (
    AdminSyncExecutionError,
    AdminSyncJobManager,
    AdminSyncJobState,
    AdminSyncOperationType,
    AdminSyncProgress,
    AdminTickerSyncState,
    ResearchDataSummaryService,
    ResearchMarketCandleSyncService,
    ResearchTickerSyncService,
)
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncFailure,
    MarketBatchSyncResult,
    MarketTickerSyncResult,
)


@pytest.mark.asyncio
async def test_freshness_service_delegates_all_summary_queries() -> None:
    class Repository:
        async def count_active_companies(self) -> int:
            return 503

        async def count_active_constituents(self, index_symbol: str) -> int:
            assert index_symbol == "^GSPC"
            return 502

        async def count_active_custom_tracked(self) -> int:
            return 3

        async def latest_candle_date(self, ticker: str) -> date:
            assert ticker == "SPY"
            return date(2026, 8, 20)

        async def active_tracked_latest_date_range(self, index_symbol: str) -> tuple[date, date]:
            assert index_symbol == "^GSPC"
            return date(2026, 8, 19), date(2026, 8, 20)

        async def count_stale_tracked_tickers(
            self, index_symbol: str, benchmark_date: date | None
        ) -> int:
            assert index_symbol == "^GSPC"
            assert benchmark_date == date(2026, 8, 20)
            return 7

        async def count_fresh_tracked_tickers(
            self, index_symbol: str, benchmark_date: date | None
        ) -> int:
            assert index_symbol == "^GSPC"
            assert benchmark_date == date(2026, 8, 20)
            return 495

        async def count_no_data_tracked_tickers(self, index_symbol: str) -> int:
            assert index_symbol == "^GSPC"
            return 3

    result = await ResearchDataSummaryService(Repository()).get_freshness()
    assert result.active_company_count == 503
    assert result.active_sp500_count == 502
    assert result.active_custom_tracked_count == 3
    assert result.earliest_active_stock_latest_date == date(2026, 8, 19)
    assert result.stale_tracked_ticker_count == 7
    assert result.fresh_tracked_ticker_count == 495
    assert result.no_data_tracked_ticker_count == 3


@pytest.mark.asyncio
async def test_ticker_sync_never_calls_provider_for_unknown_company() -> None:
    class Companies:
        async def get_company(self, ticker: str) -> None:
            return None

    class Sync:
        async def sync_ticker(self, ticker: str, start: date, end: date) -> MarketTickerSyncResult:
            raise AssertionError("provider must not be called")

    ticker, state = await ResearchTickerSyncService(Companies(), Sync()).sync(
        "fake", date(2026, 1, 1), date(2026, 8, 20)
    )
    assert ticker == "FAKE"
    assert state == AdminTickerSyncState.COMPANY_NOT_FOUND


@pytest.mark.asyncio
async def test_market_candle_sync_targets_spy_sp500_and_custom_tickers() -> None:
    class Targets:
        async def list_market_sync_targets(self, index_symbol: str) -> list[str]:
            assert index_symbol == "^GSPC"
            return ["AAPL", "SBET"]

    class Sync:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        async def sync_tickers(
            self, tickers: list[str], start: date, end: date
        ) -> MarketBatchSyncResult:
            self.calls.append(tickers)
            return MarketBatchSyncResult(
                total_active=len(tickers),
                attempted=len(tickers),
                synced=len(tickers),
                skipped=0,
                failures=(),
                next_offset=None,
            )

    sync = Sync()
    progress: list[AdminSyncProgress] = []
    result = await ResearchMarketCandleSyncService(Targets(), sync).sync(
        start=date(2026, 1, 1),
        end=date(2026, 8, 25),
        batch_size=100,
        progress_callback=progress.append,
    )
    assert sync.calls == [["SPY"], ["AAPL", "SBET"]]
    assert result.synced == 3
    assert progress[-1].attempted == 3
    assert progress[0].stage == "benchmark"
    assert progress[0].current_ticker == "SPY"
    assert any(item.stage == "stock_candles" and item.current_ticker == "AAPL" for item in progress)
    assert result.stage == "complete"


@pytest.mark.asyncio
async def test_benchmark_feed_failure_marks_job_failed_with_safe_metadata() -> None:
    manager = AdminSyncJobManager()
    failure = MarketBatchSyncFailure(
        ticker="SPY",
        error="Alpaca rejected the configured SIP data feed for the current credentials.",
        code="MARKET_DATA_FEED_NOT_AUTHORIZED",
        provider="Alpaca",
        feed="sip",
    )

    async def operation(progress: object) -> object:
        raise AdminSyncExecutionError(stage="benchmark", ticker="SPY", failure=failure)

    snapshot, started = await manager.start(
        start=date(2026, 1, 1),
        end=date(2026, 8, 25),
        operation=operation,  # type: ignore[arg-type]
        operation_type=AdminSyncOperationType.MARKET_CANDLES_SYNC,
        provider="Alpaca",
        feed="sip",
    )
    assert started is True
    for _ in range(20):
        await __import__("asyncio").sleep(0)
        current = await manager.get(snapshot.job_id)
        if current and current.state == AdminSyncJobState.FAILED:
            break
    assert current is not None
    assert current.state == AdminSyncJobState.FAILED
    assert current.failed_stage == "benchmark"
    assert current.failed_ticker == "SPY"
    assert current.error_code == "MARKET_DATA_FEED_NOT_AUTHORIZED"
    assert current.feed == "sip"
    assert "credential" not in current.error.lower() or "current credentials" in current.error
    await manager.reset()
