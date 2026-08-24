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

from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.backtesting.strategy_universe import (
    StrategyUniverseRow,
    StrategyUniverseRunner,
    build_strategy_universe_summary,
)
from alphapilot.database.session import get_db
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import (
    DailyCandleRepository,
)
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run one trading strategy across the active S&P 500 universe.")
    )

    parser.add_argument(
        "--strategy",
        choices=[strategy.value for strategy in StrategyName],
        required=True,
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
        "--capital",
        type=Decimal,
        default=Decimal("100000"),
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
        "--exit-mode",
        choices=[mode.value for mode in TrendExitMode],
        default=TrendExitMode.EMA50.value,
    )

    parser.add_argument(
        "--hybrid-trend-threshold-pct",
        type=Decimal,
        default=Decimal("3"),
    )

    parser.add_argument(
        "--micho-entry-mode",
        choices=[mode.value for mode in MichoEntryMode],
        default=MichoEntryMode.BOTH.value,
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


def build_report_base_name(
    *,
    strategy_name: StrategyName,
    exit_mode: TrendExitMode,
    hybrid_trend_threshold_pct: Decimal,
    micho_entry_mode: MichoEntryMode,
    start: date,
    end: date,
) -> str:
    safe_strategy_name = strategy_name.value.replace(
        "-",
        "_",
    )

    strategy_suffix = safe_strategy_name

    if strategy_name == StrategyName.EMA20_PULLBACK:
        safe_exit_mode = exit_mode.value.replace(
            "-",
            "_",
        )

        strategy_suffix += f"_{safe_exit_mode}"

        if exit_mode == TrendExitMode.HYBRID:
            threshold = str(hybrid_trend_threshold_pct).replace(
                ".",
                "_",
            )

            strategy_suffix += f"_{threshold}pct"

    if strategy_name == StrategyName.MICHO_150:
        safe_micho_entry_mode = micho_entry_mode.value.replace(
            "-",
            "_",
        )

        strategy_suffix += f"_{safe_micho_entry_mode}"

    return f"strategy_universe_{strategy_suffix}_{start}_{end}"


async def run_strategy_universe(
    args: argparse.Namespace,
) -> None:
    if args.start > args.end:
        raise ValueError("start must be before or equal to end")

    if args.offset < 0:
        raise ValueError("offset must not be negative")

    if args.limit is not None and args.limit <= 0:
        raise ValueError("limit must be greater than zero")

    if args.capital <= 0:
        raise ValueError("capital must be greater than zero")

    if args.hybrid_trend_threshold_pct < 0:
        raise ValueError("hybrid_trend_threshold_pct must not be negative")

    strategy_name = StrategyName(args.strategy)

    exit_mode = TrendExitMode(args.exit_mode)

    micho_entry_mode = MichoEntryMode(args.micho_entry_mode)

    db_generator = get_db()

    session = await anext(db_generator)

    try:
        company_repository = CompanyRepository(session)

        candle_repository = DailyCandleRepository(session)

        universe_repository = IndexConstituentRepository(session)

        company_service = CompanyService(company_repository)

        candle_service = DailyCandleService(candle_repository)

        runner = StrategyUniverseRunner(
            company_service=company_service,
            candle_service=candle_service,
            universe_repository=universe_repository,
            strategy_name=strategy_name,
            exit_mode=exit_mode,
            hybrid_trend_threshold_pct=(args.hybrid_trend_threshold_pct),
            micho_entry_mode=micho_entry_mode,
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

        base_name = build_report_base_name(
            strategy_name=strategy_name,
            exit_mode=exit_mode,
            hybrid_trend_threshold_pct=(args.hybrid_trend_threshold_pct),
            micho_entry_mode=micho_entry_mode,
            start=args.start,
            end=args.end,
        )

        csv_path = args.output_dir / f"{base_name}.csv"

        summary_path = args.output_dir / f"{base_name}_summary.txt"

        field_names = [field.name for field in fields(StrategyUniverseRow)]

        rows: list[StrategyUniverseRow] = []

        total = len(tickers)

        print()
        print("AlphaPilot Strategy Universe Backtest")

        print(f"Strategy: {strategy_name.value}")

        if strategy_name == StrategyName.EMA20_PULLBACK:
            print(f"Exit mode: {exit_mode.value}")

            if exit_mode == TrendExitMode.HYBRID:
                print(f"Hybrid trend threshold: {args.hybrid_trend_threshold_pct:.2f}%")

        if strategy_name == StrategyName.MICHO_150:
            print(f"Micho entry mode: {micho_entry_mode.value}")

        print(f"Tickers: {total}")

        print(f"Period: {args.start} -> {args.end}")

        print(f"Initial capital: ${args.capital:.2f}")

        print(f"Position size: {args.position_size_pct:.2f}%")

        print(f"Commission: ${args.commission:.2f}")

        print(f"Slippage: {args.slippage_bps:.2f} bps")

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
                    row = await runner.run_ticker(
                        ticker=ticker,
                        start=args.start,
                        end=args.end,
                        portfolio_config=config,
                    )

                    status = "OK"

                except Exception as exc:
                    await session.rollback()

                    row = StrategyUniverseRow(
                        ticker=ticker,
                        strategy=(strategy_name.value),
                        micho_entry_mode=(
                            micho_entry_mode.value
                            if (strategy_name == StrategyName.MICHO_150)
                            else None
                        ),
                        exit_mode=(
                            exit_mode.value
                            if (strategy_name == StrategyName.EMA20_PULLBACK)
                            else None
                        ),
                        hybrid_trend_threshold_pct=(
                            args.hybrid_trend_threshold_pct
                            if (
                                strategy_name == StrategyName.EMA20_PULLBACK
                                and exit_mode == TrendExitMode.HYBRID
                            )
                            else None
                        ),
                        status="error",
                        error=(f"{type(exc).__name__}: {exc}"),
                    )

                    status = "ERROR"

                rows.append(row)

                writer.writerow(asdict(row))

                csv_file.flush()

                print(f"[{index}/{total}] {ticker}: {status}")

        summary = build_strategy_universe_summary(
            rows,
            strategy_name=strategy_name,
            start=args.start,
            end=args.end,
        )

        summary_path.write_text(
            summary,
            encoding="utf-8",
        )

        print()
        print("=" * 60)

        print("Strategy universe backtest completed")

        print(f"CSV:     {csv_path}")

        print(f"Summary: {summary_path}")

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
        run_strategy_universe(args),
        loop_factory=create_event_loop,
    )


if __name__ == "__main__":
    main()
