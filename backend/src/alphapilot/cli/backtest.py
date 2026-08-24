from __future__ import annotations

import argparse
import asyncio
import selectors
import sys
from datetime import date, timedelta
from decimal import Decimal

from alphapilot.backtesting.models import (
    PortfolioConfig,
)
from alphapilot.backtesting.service import (
    BacktestService,
)
from alphapilot.database.session import get_db
from alphapilot.repositories.company import (
    CompanyRepository,
)
from alphapilot.repositories.daily_candle import (
    DailyCandleRepository,
)
from alphapilot.services.company import (
    CompanyService,
)
from alphapilot.services.daily_candle import (
    DailyCandleService,
)
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.factory import (
    create_strategy,
    get_strategy_stock_warmup_days,
)
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def parse_args() -> argparse.Namespace:
    default_end = date.today() - timedelta(days=1)

    default_start = default_end - timedelta(days=120)

    parser = argparse.ArgumentParser(description=("Run an AlphaPilot historical backtest"))

    parser.add_argument(
        "ticker",
        help="Company ticker to backtest",
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
        help="Initial portfolio capital",
    )

    parser.add_argument(
        "--position-size-pct",
        type=Decimal,
        default=Decimal("100"),
        help="Percentage of available cash per position",
    )

    parser.add_argument(
        "--commission",
        type=Decimal,
        default=Decimal("0"),
        help="Commission per order",
    )

    parser.add_argument(
        "--slippage-bps",
        type=Decimal,
        default=Decimal("0"),
        help="Slippage in basis points",
    )

    parser.add_argument(
        "--exit-mode",
        choices=[mode.value for mode in TrendExitMode],
        default=TrendExitMode.EMA50.value,
        help=("Trend exit rule (default: ema50)"),
    )

    parser.add_argument(
        "--hybrid-trend-threshold-pct",
        type=Decimal,
        default=Decimal("3"),
        help=("Minimum EMA20-vs-EMA50 spread for HYBRID strong-trend mode"),
    )

    parser.add_argument(
        "--strategy",
        choices=[strategy.value for strategy in StrategyName],
        default=StrategyName.EMA20_PULLBACK.value,
        help="Trading strategy to backtest",
    )

    return parser.parse_args()


async def run_backtest(
    args: argparse.Namespace,
) -> None:
    db_generator = get_db()

    session = await anext(db_generator)

    try:
        company_repository = CompanyRepository(session)

        candle_repository = DailyCandleRepository(session)

        company_service = CompanyService(company_repository)

        candle_service = DailyCandleService(candle_repository)

        strategy_name = StrategyName(args.strategy)

        strategy = create_strategy(
            strategy_name,
            exit_mode=TrendExitMode(args.exit_mode),
            hybrid_trend_threshold_pct=(args.hybrid_trend_threshold_pct),
        )

        service = BacktestService(
            company_service=company_service,
            candle_service=candle_service,
            strategy=strategy,
            stock_warmup_days=(get_strategy_stock_warmup_days(strategy_name)),
        )

        config = PortfolioConfig(
            initial_capital=args.capital,
            position_size_pct=(args.position_size_pct),
            commission_per_order=(args.commission),
            slippage_bps=(args.slippage_bps),
        )

        result = await service.run(
            ticker=args.ticker,
            start=args.start,
            end=args.end,
            portfolio_config=config,
        )

        backtest = result.backtest
        metrics = result.metrics
        portfolio = result.portfolio
        portfolio_metrics = result.portfolio_metrics
        diagnostics = result.diagnostics

        buy_and_hold = result.buy_and_hold

        buy_and_hold_metrics = result.buy_and_hold_metrics

        spy_buy_and_hold = result.spy_buy_and_hold

        spy_buy_and_hold_metrics = result.spy_buy_and_hold_metrics

        buy_signals = sum(1 for bar in backtest.bars if bar.signal == Signal.BUY)

        sell_signals = sum(1 for bar in backtest.bars if bar.signal == Signal.SELL)

        hold_signals = sum(1 for bar in backtest.bars if bar.signal == Signal.HOLD)

        print()
        print("=" * 60)
        print(f"AlphaPilot Backtest — {backtest.ticker}")
        print("=" * 60)

        print(f"Period: {backtest.start} -> {backtest.end}")

        print(f"Evaluated bars: {backtest.total_bars}")

        print()
        print("Signals")
        print("-------")

        print(f"BUY:  {buy_signals}")

        print(f"SELL: {sell_signals}")

        print(f"HOLD: {hold_signals}")

        print()
        print("Trades")
        print("------")

        print(f"Completed trades: {metrics.total_trades}")

        print(f"Winning trades: {metrics.winning_trades}")

        print(f"Losing trades: {metrics.losing_trades}")

        print(f"Win rate: {metrics.win_rate_pct:.2f}%")

        if metrics.average_return_pct is not None:
            print(f"Average trade: {metrics.average_return_pct:.2f}%")

        if metrics.average_win_pct is not None:
            print(f"Average win: {metrics.average_win_pct:.2f}%")

        if metrics.average_loss_pct is not None:
            print(f"Average loss: {metrics.average_loss_pct:.2f}%")

        if metrics.profit_factor is not None:
            print(f"Profit factor: {metrics.profit_factor:.2f}")
        else:
            print("Profit factor: N/A")

        print()
        print("Portfolio")
        print("---------")
        print(
            f"CAGR: {portfolio_metrics.cagr_pct:.2f}%"
            if portfolio_metrics.cagr_pct is not None
            else "CAGR: N/A"
        )

        print(f"Max drawdown: {portfolio_metrics.max_drawdown_pct:.2f}%")

        print(
            f"Sharpe ratio: {portfolio_metrics.sharpe_ratio:.2f}"
            if portfolio_metrics.sharpe_ratio is not None
            else "Sharpe ratio: N/A"
        )

        print(f"Exposure: {portfolio_metrics.exposure_pct:.2f}%")

        print(
            f"Average holding: {portfolio_metrics.average_holding_days:.1f} days"
            if portfolio_metrics.average_holding_days is not None
            else "Average holding: N/A"
        )

        print(f"Initial capital: ${portfolio.initial_capital:.2f}")

        print(f"Final equity: ${portfolio.final_equity:.2f}")

        print(f"Total return: {portfolio.total_return_pct:.2f}%")

        if portfolio.open_position is not None:
            print(
                "Open position: "
                f"{portfolio.open_position.shares} "
                f"shares @ "
                f"${portfolio.open_position.entry_price:.2f}"
            )
        else:
            print("Open position: None")

        print(
            f"Average MFE: {diagnostics.average_mfe_pct:.2f}%"
            if diagnostics.average_mfe_pct is not None
            else "Average MFE: N/A"
        )

        print(
            f"Average MAE: {diagnostics.average_mae_pct:.2f}%"
            if diagnostics.average_mae_pct is not None
            else "Average MAE: N/A"
        )

        print(
            f"Average peak giveback: {diagnostics.average_peak_giveback_pct:.2f}%"
            if diagnostics.average_peak_giveback_pct is not None
            else "Average peak giveback: N/A"
        )

        print()
        print("Benchmarks")
        print("----------")

        print(f"{backtest.ticker} Buy & Hold")

        print(f"  Final equity: ${buy_and_hold.final_equity:.2f}")

        print(f"  Total return: {buy_and_hold.total_return_pct:.2f}%")

        print(
            f"  CAGR: {buy_and_hold_metrics.cagr_pct:.2f}%"
            if buy_and_hold_metrics.cagr_pct is not None
            else "  CAGR: N/A"
        )

        print(f"  Max drawdown: {buy_and_hold_metrics.max_drawdown_pct:.2f}%")

        print(
            f"  Sharpe ratio: {buy_and_hold_metrics.sharpe_ratio:.2f}"
            if buy_and_hold_metrics.sharpe_ratio is not None
            else "  Sharpe ratio: N/A"
        )

        print()

        print("SPY Buy & Hold")

        print(f"  Final equity: ${spy_buy_and_hold.final_equity:.2f}")

        print(f"  Total return: {spy_buy_and_hold.total_return_pct:.2f}%")

        print(
            f"  CAGR: {spy_buy_and_hold_metrics.cagr_pct:.2f}%"
            if spy_buy_and_hold_metrics.cagr_pct is not None
            else "  CAGR: N/A"
        )

        print(f"  Max drawdown: {spy_buy_and_hold_metrics.max_drawdown_pct:.2f}%")

        print(
            f"  Sharpe ratio: {spy_buy_and_hold_metrics.sharpe_ratio:.2f}"
            if spy_buy_and_hold_metrics.sharpe_ratio is not None
            else "  Sharpe ratio: N/A"
        )

        print()

        print("Strategy vs Benchmarks")
        print("----------------------")

        print(
            f"Return gap vs {backtest.ticker} Buy & Hold: "
            f"{portfolio.total_return_pct - buy_and_hold.total_return_pct:+.2f} pp"
        )

        print(
            "Return gap vs SPY Buy & Hold: "
            f"{portfolio.total_return_pct - spy_buy_and_hold.total_return_pct:+.2f} pp"
        )
        print(f"Strategy: {strategy_name.value}")

        if strategy_name == StrategyName.EMA20_PULLBACK:
            print(f"Exit mode: {args.exit_mode.upper()}")

            if args.exit_mode == TrendExitMode.HYBRID.value:
                print(f"Hybrid trend threshold: {args.hybrid_trend_threshold_pct:.2f}%")

        # END OF TEST PROFILE
        print()
        print("=" * 60)

    finally:
        await db_generator.aclose()


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    return asyncio.new_event_loop()


def main() -> None:
    args = parse_args()

    asyncio.run(
        run_backtest(args),
        loop_factory=create_event_loop,
    )


if __name__ == "__main__":
    main()
