from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import selectors
import sys
from dataclasses import asdict, fields
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.backtesting.universe_comparison import (
    UniverseExitComparisonRow,
    UniverseExitComparisonRunner,
    build_universe_summary,
)
from alphapilot.database.session import get_db
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService


def parse_args() -> argparse.Namespace:
    default_end = date.today() - timedelta(days=1)
    default_start = default_end - timedelta(days=365 * 5)

    parser = argparse.ArgumentParser(
        description=("Compare EMA20 and EMA50 exits across the active S&P 500 universe.")
    )

    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=default_start,
        help="Backtest start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=default_end,
        help="Backtest end date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--capital",
        type=Decimal,
        default=Decimal("100000"),
        help="Initial capital for each ticker backtest",
    )

    parser.add_argument(
        "--position-size-pct",
        type=Decimal,
        default=Decimal("100"),
    )

    parser.add_argument(
        "--commission",
        type=Decimal,
        default=Decimal("0"),
    )

    parser.add_argument(
        "--slippage-bps",
        type=Decimal,
        default=Decimal("0"),
    )

    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip the first N alphabetically sorted tickers",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only N tickers (useful for smoke tests)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest_reports"),
        help="Directory for CSV and TXT reports",
    )

    return parser.parse_args()


async def run_universe_backtest(
    args: argparse.Namespace,
) -> None:
    if args.start > args.end:
        raise ValueError("start must be before or equal to end")

    if args.offset < 0:
        raise ValueError("offset must not be negative")

    if args.limit is not None and args.limit <= 0:
        raise ValueError("limit must be greater than zero")

    db_generator = get_db()
    session = await anext(db_generator)

    try:
        company_service = CompanyService(
            CompanyRepository(session),
        )

        candle_service = DailyCandleService(
            DailyCandleRepository(session),
        )

        universe_repository = IndexConstituentRepository(session)

        runner = UniverseExitComparisonRunner(
            company_service=company_service,
            candle_service=candle_service,
            universe_repository=universe_repository,
        )

        tickers = await runner.list_tickers()

        if args.offset:
            tickers = tickers[args.offset :]

        if args.limit is not None:
            tickers = tickers[: args.limit]

        config = PortfolioConfig(
            initial_capital=args.capital,
            position_size_pct=(args.position_size_pct),
            commission_per_order=(args.commission),
            slippage_bps=(args.slippage_bps),
        )

        args.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        report_name = f"universe_exit_comparison_{args.start}_{args.end}"

        csv_path = args.output_dir / f"{report_name}.csv"

        summary_path = args.output_dir / f"{report_name}_summary.txt"

        field_names = [field.name for field in fields(UniverseExitComparisonRow)]

        rows: list[UniverseExitComparisonRow] = []

        total = len(tickers)

        print()
        print("AlphaPilot Universe Exit Comparison")
        print(f"Tickers: {total}")
        print(f"Period: {args.start} -> {args.end}")
        print(f"CSV: {csv_path}")
        print()

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=field_names,
            )

            writer.writeheader()

            for index, ticker in enumerate(
                tickers,
                start=1,
            ):
                try:
                    row = await runner.compare_ticker(
                        ticker=ticker,
                        start=args.start,
                        end=args.end,
                        portfolio_config=config,
                    )

                    status_text = "OK"

                except Exception as exc:
                    await session.rollback()

                    row = UniverseExitComparisonRow(
                        ticker=ticker,
                        status="error",
                        error=(f"{type(exc).__name__}: {exc}"),
                    )

                    status_text = "ERROR"

                rows.append(row)

                writer.writerow(asdict(row))

                csv_file.flush()

                print(f"[{index}/{total}] {ticker}: {status_text}")

        summary = build_universe_summary(
            rows,
            start=args.start,
            end=args.end,
        )

        summary_path.write_text(
            summary,
            encoding="utf-8",
        )

        print()
        print("=" * 60)
        print("Universe comparison completed")
        print(f"CSV report: {csv_path}")
        print(f"Summary:    {summary_path}")
        print("=" * 60)

    finally:
        await db_generator.aclose()


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    return asyncio.new_event_loop()


def main() -> None:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    args = parse_args()

    asyncio.run(
        run_universe_backtest(args),
        loop_factory=create_event_loop,
    )


if __name__ == "__main__":
    main()
