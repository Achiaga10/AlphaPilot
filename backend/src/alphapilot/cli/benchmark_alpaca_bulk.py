from __future__ import annotations

import asyncio
import selectors
import sys
import time
from datetime import date, timedelta

from alphapilot.database.session import get_db
from alphapilot.market.providers.alpaca import (
    AlpacaProvider,
)
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)

INDEX_SYMBOL = "^GSPC"
BENCHMARK_SIZE = 100


async def run_benchmark() -> None:
    db_generator = get_db()

    session = await anext(db_generator)

    try:
        repository = IndexConstituentRepository(session)

        constituents = await repository.list_active(INDEX_SYMBOL)

        tickers = [constituent.ticker for constituent in constituents[:BENCHMARK_SIZE]]

        end = date.today() - timedelta(days=1)

        start = end - timedelta(days=120)

        provider = AlpacaProvider()

        print(f"Downloading {len(tickers)} tickers from Alpaca...")

        started_at = time.perf_counter()

        result = await provider.get_history_many(
            tickers=tickers,
            start=start,
            end=end,
        )

        elapsed = time.perf_counter() - started_at

        total_candles = sum(len(candles) for candles in result.values())

        symbols_with_data = sum(1 for candles in result.values() if candles)

        print()
        print("Alpaca bulk benchmark")
        print("---------------------")

        print(f"Tickers requested: {len(tickers)}")

        print(f"Tickers with data: {symbols_with_data}")

        print(f"Total candles: {total_candles}")

        print(f"Elapsed seconds: {elapsed:.2f}")

        if elapsed > 0:
            print(f"Candles / second: {total_candles / elapsed:.2f}")

    finally:
        await db_generator.aclose()


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    return asyncio.new_event_loop()


def main() -> None:
    asyncio.run(
        run_benchmark(),
        loop_factory=create_event_loop,
    )


if __name__ == "__main__":
    main()
