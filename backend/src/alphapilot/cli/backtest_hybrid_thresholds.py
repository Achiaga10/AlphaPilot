from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import selectors
import sys
from dataclasses import asdict, fields
from datetime import date
from decimal import Decimal
from pathlib import Path

from alphapilot.backtesting.hybrid_threshold_experiment import (
    HybridThresholdAggregate,
    HybridThresholdExperimentRunner,
    HybridThresholdRow,
    aggregate_thresholds,
    build_threshold_summary,
    select_threshold,
)
from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.database.session import get_db
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run HYBRID exit threshold experiments across the active S&P 500 universe.")
    )

    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        required=True,
    )

    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        required=True,
    )

    parser.add_argument(
        "--thresholds",
        type=Decimal,
        nargs="+",
        default=[
            Decimal("1"),
            Decimal("2"),
            Decimal("3"),
            Decimal("4"),
            Decimal("5"),
        ],
    )

    parser.add_argument(
        "--capital",
        type=Decimal,
        default=Decimal("100000"),
    )

    parser.add_argument(
        "--offset",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest_reports"),
    )

    return parser.parse_args()


async def run_experiment(
    args: argparse.Namespace,
) -> None:
    if args.start > args.end:
        raise ValueError("start must be before or equal to end")

    if args.offset < 0:
        raise ValueError("offset must not be negative")

    if args.limit is not None and args.limit <= 0:
        raise ValueError("limit must be greater than zero")

    thresholds = sorted(set(args.thresholds))

    if any(threshold < 0 for threshold in thresholds):
        raise ValueError("thresholds must not be negative")

    db_generator = get_db()
    session = await anext(db_generator)

    try:
        runner = HybridThresholdExperimentRunner(
            company_service=CompanyService(CompanyRepository(session)),
            candle_service=DailyCandleService(DailyCandleRepository(session)),
            universe_repository=(IndexConstituentRepository(session)),
        )

        tickers = await runner.list_tickers()

        if args.offset:
            tickers = tickers[args.offset :]

        if args.limit is not None:
            tickers = tickers[: args.limit]

        config = PortfolioConfig(
            initial_capital=args.capital,
        )

        args.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        base_name = f"hybrid_threshold_development_{args.start}_{args.end}"

        detail_path = args.output_dir / f"{base_name}.csv"

        aggregate_path = args.output_dir / f"{base_name}_aggregates.csv"

        summary_path = args.output_dir / f"{base_name}_summary.txt"

        row_fields = [field.name for field in fields(HybridThresholdRow)]

        rows: list[HybridThresholdRow] = []

        total_runs = len(tickers) * len(thresholds)

        completed_runs = 0

        print()
        print("AlphaPilot HYBRID Threshold Experiment")
        print(f"Tickers: {len(tickers)}")
        print("Thresholds: " + ", ".join(f"{threshold}%" for threshold in thresholds))
        print(f"Total runs: {total_runs}")
        print()

        with detail_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=row_fields,
            )

            writer.writeheader()

            for threshold in thresholds:
                for ticker in tickers:
                    completed_runs += 1

                    try:
                        row = await runner.run_ticker(
                            ticker=ticker,
                            threshold_pct=threshold,
                            start=args.start,
                            end=args.end,
                            portfolio_config=config,
                        )

                        status = "OK"

                    except Exception as exc:
                        await session.rollback()

                        row = HybridThresholdRow(
                            ticker=ticker,
                            threshold_pct=threshold,
                            status="error",
                            error=(f"{type(exc).__name__}: {exc}"),
                        )

                        status = "ERROR"

                    rows.append(row)

                    writer.writerow(asdict(row))

                    csv_file.flush()

                    print(
                        f"[{completed_runs}/{total_runs}] {ticker} threshold={threshold}% {status}"
                    )

        aggregates = aggregate_thresholds(
            rows,
            thresholds,
        )

        selected = select_threshold(aggregates)

        aggregate_fields = [field.name for field in fields(HybridThresholdAggregate)]

        with aggregate_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as aggregate_file:
            writer = csv.DictWriter(
                aggregate_file,
                fieldnames=aggregate_fields,
            )

            writer.writeheader()

            for aggregate in aggregates:
                writer.writerow(asdict(aggregate))

        summary = build_threshold_summary(
            aggregates,
            selected=selected,
            start=args.start,
            end=args.end,
            universe_size=len(tickers),
        )

        summary_path.write_text(
            summary,
            encoding="utf-8",
        )

        print()
        print("=" * 60)
        print("Threshold experiment completed")
        print(f"Selected threshold: {selected.threshold_pct:.2f}%")
        print(f"Details:    {detail_path}")
        print(f"Aggregates: {aggregate_path}")
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
        run_experiment(args),
        loop_factory=create_event_loop,
    )


if __name__ == "__main__":
    main()
