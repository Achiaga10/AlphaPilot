from __future__ import annotations

import argparse
import asyncio
import selectors
import sys
from datetime import date, timedelta
from pathlib import Path

from alphapilot.database.session import get_db
from alphapilot.market.providers.alpaca import AlpacaProvider
from alphapilot.repositories.company import (
    CompanyRepository,
)
from alphapilot.repositories.daily_candle import (
    DailyCandleRepository,
)
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.alpaca_bulk_market_sync import (
    AlpacaBulkMarketSyncService,
)
from alphapilot.services.company import (
    CompanyService,
)
from alphapilot.services.daily_candle import (
    DailyCandleService,
)
from alphapilot.services.market_batch_sync import (
    MarketBatchSyncResult,
)
from alphapilot.services.universe_market_sync_runner import (
    UniverseMarketSyncRunner,
)

SP500_INDEX_SYMBOL = "^GSPC"
DEFAULT_BATCH_SIZE = 100
CHECKPOINT_PATH = Path.home() / ".alphapilot" / "universe_market_sync_checkpoint.json"


def parse_date(
    value: str,
) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD format") from exc


def print_progress(
    result: MarketBatchSyncResult,
) -> None:
    processed = result.next_offset if result.next_offset is not None else result.total_active

    print(
        f"[{processed}/{result.total_active}] "
        f"attempted={result.attempted} "
        f"synced={result.synced} "
        f"skipped={result.skipped} "
        f"failed={len(result.failures)}"
    )

    for failure in result.failures:
        print(f"  FAILED {failure.ticker}: {failure.error}")


async def run_sync(
    args: argparse.Namespace,
) -> None:
    db_generator = get_db()

    session = await anext(db_generator)

    try:
        company_repository = CompanyRepository(session)
        universe_repository = IndexConstituentRepository(session)
        candle_repository = DailyCandleRepository(session)

        company_service = CompanyService(company_repository)
        candle_service = DailyCandleService(candle_repository)

        provider = AlpacaProvider()

        batch_service = AlpacaBulkMarketSyncService(
            provider=provider,
            universe_repository=universe_repository,
            company_service=company_service,
            candle_service=candle_service,
        )

        runner = UniverseMarketSyncRunner(
            batch_sync_service=batch_service,
            company_service=company_service,
            checkpoint_path=CHECKPOINT_PATH,
        )

        summary = await runner.run(
            index_symbol=SP500_INDEX_SYMBOL,
            start=args.start,
            end=args.end,
            batch_size=args.batch_size,
            resume=not args.no_resume,
            progress_callback=print_progress,
        )

        print()
        print("Universe market sync completed")
        print(f"Total active: {summary.total_active}")
        print(f"Attempted: {summary.attempted}")
        print(f"Synced: {summary.synced}")
        print(f"Skipped: {summary.skipped}")
        print(f"Failures: {len(summary.failures)}")
        print(f"Benchmark SPY: {'synced' if summary.benchmark_synced else 'failed'}")

        if summary.failures:
            print()
            print("Failed tickers:")

            for failure in summary.failures:
                print(f"- {failure.ticker}: {failure.error}")

    finally:
        await db_generator.aclose()


def build_parser() -> argparse.ArgumentParser:
    today = date.today() - timedelta(days=1)

    parser = argparse.ArgumentParser(
        description=("Synchronize historical market data for the active S&P 500 universe.")
    )

    parser.add_argument(
        "--start",
        type=parse_date,
        default=(today - timedelta(days=120)),
        help=("History start date (YYYY-MM-DD)"),
    )

    parser.add_argument(
        "--end",
        type=parse_date,
        default=today,
        help=("History end date (YYYY-MM-DD)"),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=("Number of constituents per checkpoint batch"),
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help=("Ignore an existing checkpoint and start again from offset 0"),
    )

    return parser


def create_event_loop() -> asyncio.AbstractEventLoop:
    """Create an event loop compatible with Psycopg on Windows."""

    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    return asyncio.new_event_loop()


def main() -> None:
    parser = build_parser()

    args = parser.parse_args()

    try:
        asyncio.run(
            run_sync(args),
            loop_factory=create_event_loop,
        )

    except KeyboardInterrupt:
        print()
        print(
            "Market sync stopped. "
            "Run the same command again "
            "to resume from the last "
            "completed batch."
        )
