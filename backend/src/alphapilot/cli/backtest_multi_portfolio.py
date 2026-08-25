from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import selectors
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import (
    MultiPortfolioBacktestService,
    MultiPortfolioRunResult,
)
from alphapilot.database.session import get_db
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.factory import create_strategy, get_strategy_stock_warmup_days
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one strategy across a shared-cash multi-stock portfolio."
    )
    parser.add_argument("--strategy", choices=[item.value for item in StrategyName], required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--capital", type=Decimal, default=Decimal("100000"))
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--commission", type=Decimal, default=Decimal("0"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("0"))
    parser.add_argument(
        "--exit-mode",
        choices=[item.value for item in TrendExitMode],
        default=TrendExitMode.EMA50.value,
    )
    parser.add_argument(
        "--hybrid-trend-threshold-pct",
        type=Decimal,
        default=Decimal("3"),
    )
    parser.add_argument(
        "--micho-entry-mode",
        choices=[item.value for item in MichoEntryMode],
        default=MichoEntryMode.BOTH.value,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest_reports/multi_portfolio"),
    )
    return parser.parse_args()


def _format_decimal(value: Decimal | None, suffix: str = "%") -> str:
    return "N/A" if value is None else f"{value:.2f}{suffix}"


def build_summary(
    result: MultiPortfolioRunResult,
    *,
    strategy_name: StrategyName,
    exit_mode: TrendExitMode,
    hybrid_threshold: Decimal,
    micho_entry_mode: MichoEntryMode,
    start: date,
    end: date,
    config: MultiPortfolioConfig,
) -> str:
    metrics = result.metrics
    lines = [
        "=" * 72,
        "AlphaPilot Multi-Stock Portfolio Backtest",
        "=" * 72,
        f"Strategy: {strategy_name.value}",
    ]

    if strategy_name == StrategyName.EMA20_PULLBACK:
        lines.append(f"Exit mode: {exit_mode.value}")

        if exit_mode == TrendExitMode.HYBRID:
            lines.append(f"Hybrid trend threshold: {hybrid_threshold:.2f}%")
    else:
        lines.append(f"Micho entry mode: {micho_entry_mode.value}")

    lines.extend(
        [
            f"Requested period: {start} -> {end}",
            (
                "Actual portfolio period: "
                f"{result.portfolio.equity_curve[0].trading_day} -> "
                f"{result.portfolio.equity_curve[-1].trading_day}"
                if result.portfolio.equity_curve
                else "Actual portfolio period: N/A"
            ),
            "Universe: current active S&P 500 constituents (^GSPC)",
            f"Successful tickers: {len(result.successful_tickers)}",
            f"Failed tickers: {len(result.failed_tickers)}",
            f"Initial capital: ${config.initial_capital:.2f}",
            f"Max positions: {config.max_positions}",
            "Sizing method: fixed equal slot (current equity / max positions)",
            f"Commission per order: ${config.commission_per_order:.2f}",
            f"Slippage: {config.slippage_bps:.2f} bps",
            f"Selection policy: {result.selection_policy_name}",
            "Selection warning: stable ticker ordering is a non-alpha engine-validation baseline.",
            "Open-position handling: marked to market at final close; not force-closed.",
            "Survivorship warning: current constituents create survivorship bias.",
            (
                "Benchmark caveat: SPY is aligned to the actual portfolio period; "
                "incomplete ticker histories remain."
            ),
            "",
            "PORTFOLIO RESULTS",
            "-----------------",
            f"Initial equity: ${metrics.initial_equity:.2f}",
            f"Final equity: ${metrics.final_equity:.2f}",
            f"Total return: {_format_decimal(metrics.total_return_pct)}",
            f"CAGR: {_format_decimal(metrics.cagr_pct)}",
            f"Max drawdown: {_format_decimal(metrics.max_drawdown_pct)}",
            f"Sharpe: {_format_decimal(metrics.sharpe_ratio, '')}",
            f"Exposure: {_format_decimal(metrics.exposure_pct)}",
            f"Completed trades: {metrics.completed_trades}",
            f"Win rate: {_format_decimal(metrics.win_rate_pct)}",
            f"Profit factor: {_format_decimal(metrics.profit_factor, '')}",
            f"Average trade: {_format_decimal(metrics.average_trade_pct)}",
            f"Turnover: {_format_decimal(metrics.turnover_pct)}",
            f"Average open positions: {_format_decimal(metrics.average_open_positions, '')}",
            f"Max concurrent positions: {metrics.max_concurrent_positions}",
            f"Open positions at end: {len(result.portfolio.open_positions)}",
            "",
            "SPY BUY & HOLD",
            "--------------",
            f"Final equity: ${result.spy_metrics.final_equity:.2f}",
            f"Total return: {_format_decimal(result.spy_metrics.total_return_pct)}",
            f"CAGR: {_format_decimal(result.spy_metrics.cagr_pct)}",
            f"Max drawdown: {_format_decimal(result.spy_metrics.max_drawdown_pct)}",
            f"Sharpe: {_format_decimal(result.spy_metrics.sharpe_ratio, '')}",
        ]
    )

    if result.failed_tickers:
        lines.extend(["", "FAILED TICKERS", "--------------"])
        lines.extend(f"{ticker}: {error}" for ticker, error in result.failed_tickers)

    lines.extend(["", "=" * 72])
    return "\n".join(lines)


def _base_name(
    strategy_name: StrategyName,
    exit_mode: TrendExitMode,
    hybrid_threshold: Decimal,
    micho_entry_mode: MichoEntryMode,
    start: date,
    end: date,
) -> str:
    suffix = strategy_name.value.replace("-", "_")

    if strategy_name == StrategyName.EMA20_PULLBACK:
        suffix += f"_{exit_mode.value.replace('-', '_')}"

        if exit_mode == TrendExitMode.HYBRID:
            suffix += f"_{str(hybrid_threshold).replace('.', '_')}pct"
    else:
        suffix += f"_{micho_entry_mode.value.replace('-', '_')}"

    return f"multi_portfolio_{suffix}_{start}_{end}"


async def run(args: argparse.Namespace) -> None:
    strategy_name = StrategyName(args.strategy)
    exit_mode = TrendExitMode(args.exit_mode)
    micho_entry_mode = MichoEntryMode(args.micho_entry_mode)
    config = MultiPortfolioConfig(
        initial_capital=args.capital,
        max_positions=args.max_positions,
        commission_per_order=args.commission,
        slippage_bps=args.slippage_bps,
    )
    strategy = create_strategy(
        strategy_name,
        exit_mode=exit_mode,
        hybrid_trend_threshold_pct=args.hybrid_trend_threshold_pct,
        micho_entry_mode=micho_entry_mode,
    )
    db_generator = get_db()
    session = await anext(db_generator)

    try:
        service = MultiPortfolioBacktestService(
            company_service=CompanyService(CompanyRepository(session)),
            candle_service=DailyCandleService(DailyCandleRepository(session)),
            universe_repository=IndexConstituentRepository(session),
            strategy=strategy,
            stock_warmup_days=get_strategy_stock_warmup_days(strategy_name),
        )
        result = await service.run(start=args.start, end=args.end, config=config)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        base_name = _base_name(
            strategy_name,
            exit_mode,
            args.hybrid_trend_threshold_pct,
            micho_entry_mode,
            args.start,
            args.end,
        )
        summary_path = args.output_dir / f"{base_name}_summary.txt"
        equity_path = args.output_dir / f"{base_name}_equity.csv"
        trades_path = args.output_dir / f"{base_name}_trades.csv"
        summary_path.write_text(
            build_summary(
                result,
                strategy_name=strategy_name,
                exit_mode=exit_mode,
                hybrid_threshold=args.hybrid_trend_threshold_pct,
                micho_entry_mode=micho_entry_mode,
                start=args.start,
                end=args.end,
                config=config,
            ),
            encoding="utf-8",
        )

        with equity_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(["trading_day", "cash", "invested_value", "equity", "open_positions"])

            for point in result.portfolio.equity_curve:
                writer.writerow(
                    [
                        point.trading_day,
                        point.cash,
                        point.invested_value,
                        point.equity,
                        point.open_positions,
                    ]
                )

        with trades_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(
                [
                    "ticker",
                    "entry_signal_day",
                    "entry_day",
                    "entry_price",
                    "exit_signal_day",
                    "exit_day",
                    "exit_price",
                    "shares",
                    "entry_commission",
                    "exit_commission",
                    "pnl",
                    "return_pct",
                    "entry_reason",
                    "exit_reason",
                ]
            )

            for trade in result.portfolio.trades:
                writer.writerow(
                    [
                        trade.ticker,
                        trade.entry_signal_day,
                        trade.entry_day,
                        trade.entry_price,
                        trade.exit_signal_day,
                        trade.exit_day,
                        trade.exit_price,
                        trade.shares,
                        trade.entry_commission,
                        trade.exit_commission,
                        trade.pnl,
                        trade.return_pct,
                        trade.entry_reason,
                        trade.exit_reason,
                    ]
                )

        print(summary_path.read_text(encoding="utf-8"))
        print(f"Summary: {summary_path}")
        print(f"Equity:  {equity_path}")
        print(f"Trades:  {trades_path}")
    finally:
        await db_generator.aclose()


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    return asyncio.new_event_loop()


def main() -> None:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    args = parse_args()
    asyncio.run(run(args), loop_factory=create_event_loop)


if __name__ == "__main__":
    main()
