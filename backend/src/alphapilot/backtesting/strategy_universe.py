from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from alphapilot.backtesting.entry_analysis import (
    EntryReasonPerformanceCalculator,
)
from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.backtesting.service import BacktestService
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.evaluation import SignalReason
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.factory import (
    create_strategy,
    get_strategy_stock_warmup_days,
)
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


@dataclass(slots=True, frozen=True)
class StrategyUniverseRow:
    ticker: str
    strategy: str

    micho_entry_mode: str | None = None

    exit_mode: str | None = None
    hybrid_trend_threshold_pct: Decimal | None = None

    status: str = "ok"
    error: str = ""

    actual_start: date | None = None
    actual_end: date | None = None
    evaluated_bars: int | None = None

    buy_signals: int | None = None
    sell_signals: int | None = None
    hold_signals: int | None = None

    breakout_buy_signals: int | None = None
    bounce_buy_signals: int | None = None

    executed_trades: int | None = None

    breakout_completed_trades: int | None = None
    breakout_win_rate_pct: Decimal | None = None
    breakout_average_trade_pct: Decimal | None = None
    breakout_average_win_pct: Decimal | None = None
    breakout_average_loss_pct: Decimal | None = None
    breakout_profit_factor: Decimal | None = None
    breakout_compounded_return_pct: Decimal | None = None
    breakout_average_holding_days: Decimal | None = None
    breakout_average_mfe_pct: Decimal | None = None
    breakout_average_mae_pct: Decimal | None = None
    breakout_peak_giveback_pct: Decimal | None = None

    bounce_completed_trades: int | None = None
    bounce_win_rate_pct: Decimal | None = None
    bounce_average_trade_pct: Decimal | None = None
    bounce_average_win_pct: Decimal | None = None
    bounce_average_loss_pct: Decimal | None = None
    bounce_profit_factor: Decimal | None = None
    bounce_compounded_return_pct: Decimal | None = None
    bounce_average_holding_days: Decimal | None = None
    bounce_average_mfe_pct: Decimal | None = None
    bounce_average_mae_pct: Decimal | None = None
    bounce_peak_giveback_pct: Decimal | None = None

    total_return_pct: Decimal | None = None
    cagr_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    sharpe_ratio: Decimal | None = None

    profit_factor: Decimal | None = None
    win_rate_pct: Decimal | None = None
    average_trade_pct: Decimal | None = None
    average_win_pct: Decimal | None = None
    average_loss_pct: Decimal | None = None

    completed_trades: int | None = None
    exposure_pct: Decimal | None = None
    average_holding_days: Decimal | None = None

    average_mfe_pct: Decimal | None = None
    average_mae_pct: Decimal | None = None
    peak_giveback_pct: Decimal | None = None

    stock_buy_hold_return_pct: Decimal | None = None
    spy_buy_hold_return_pct: Decimal | None = None


class StrategyUniverseRunner:
    """Runs one strategy across the active S&P 500 universe."""

    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        universe_repository: IndexConstituentRepository,
        *,
        strategy_name: StrategyName,
        exit_mode: TrendExitMode = TrendExitMode.EMA50,
        hybrid_trend_threshold_pct: Decimal = Decimal("3"),
        micho_entry_mode: MichoEntryMode = MichoEntryMode.BOTH,
    ) -> None:
        self.strategy_name = strategy_name
        self.universe_repository = universe_repository
        self.exit_mode = exit_mode
        self.hybrid_trend_threshold_pct = hybrid_trend_threshold_pct
        self.micho_entry_mode = micho_entry_mode

        strategy = create_strategy(
            strategy_name,
            exit_mode=exit_mode,
            hybrid_trend_threshold_pct=hybrid_trend_threshold_pct,
            micho_entry_mode=micho_entry_mode,
        )

        self.backtest_service = BacktestService(
            company_service=company_service,
            candle_service=candle_service,
            strategy=strategy,
            stock_warmup_days=get_strategy_stock_warmup_days(strategy_name),
        )

    async def list_tickers(
        self,
    ) -> list[str]:
        constituents = await self.universe_repository.list_active(self.SP500_INDEX_SYMBOL)

        return sorted({constituent.ticker.upper() for constituent in constituents})

    async def run_ticker(
        self,
        *,
        ticker: str,
        start: date,
        end: date,
        portfolio_config: PortfolioConfig,
    ) -> StrategyUniverseRow:
        result = await self.backtest_service.run(
            ticker=ticker,
            start=start,
            end=end,
            portfolio_config=portfolio_config,
        )

        buy_signals = sum(1 for bar in result.backtest.bars if bar.signal == Signal.BUY)

        sell_signals = sum(1 for bar in result.backtest.bars if bar.signal == Signal.SELL)

        hold_signals = sum(1 for bar in result.backtest.bars if bar.signal == Signal.HOLD)

        breakout_buy_signals = sum(
            1
            for bar in result.backtest.bars
            if (bar.evaluation.reason == SignalReason.MICHO_150_BREAKOUT)
        )

        bounce_buy_signals = sum(
            1
            for bar in result.backtest.bars
            if (bar.evaluation.reason == SignalReason.MICHO_150_BOUNCE)
        )

        entry_analysis = EntryReasonPerformanceCalculator()

        breakout_performance = entry_analysis.calculate(
            result.diagnostics,
            reason=SignalReason.MICHO_150_BREAKOUT,
        )

        bounce_performance = entry_analysis.calculate(
            result.diagnostics,
            reason=SignalReason.MICHO_150_BOUNCE,
        )

        return StrategyUniverseRow(
            ticker=ticker,
            strategy=self.strategy_name.value,
            micho_entry_mode=(
                self.micho_entry_mode.value
                if self.strategy_name == StrategyName.MICHO_150
                else None
            ),
            exit_mode=(
                self.exit_mode.value if self.strategy_name == StrategyName.EMA20_PULLBACK else None
            ),
            hybrid_trend_threshold_pct=(
                self.hybrid_trend_threshold_pct
                if (
                    self.strategy_name == StrategyName.EMA20_PULLBACK
                    and self.exit_mode == TrendExitMode.HYBRID
                )
                else None
            ),
            actual_start=result.backtest.start,
            actual_end=result.backtest.end,
            evaluated_bars=result.backtest.total_bars,
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            hold_signals=hold_signals,
            breakout_buy_signals=breakout_buy_signals,
            bounce_buy_signals=bounce_buy_signals,
            executed_trades=len(result.portfolio.trades),
            breakout_completed_trades=(breakout_performance.total_trades),
            breakout_win_rate_pct=(breakout_performance.win_rate_pct),
            breakout_average_trade_pct=(breakout_performance.average_trade_pct),
            breakout_average_win_pct=(breakout_performance.average_win_pct),
            breakout_average_loss_pct=(breakout_performance.average_loss_pct),
            breakout_profit_factor=(breakout_performance.profit_factor),
            breakout_compounded_return_pct=(breakout_performance.compounded_return_pct),
            breakout_average_holding_days=(breakout_performance.average_holding_days),
            breakout_average_mfe_pct=(breakout_performance.average_mfe_pct),
            breakout_average_mae_pct=(breakout_performance.average_mae_pct),
            breakout_peak_giveback_pct=(breakout_performance.average_peak_giveback_pct),
            bounce_completed_trades=(bounce_performance.total_trades),
            bounce_win_rate_pct=(bounce_performance.win_rate_pct),
            bounce_average_trade_pct=(bounce_performance.average_trade_pct),
            bounce_average_win_pct=(bounce_performance.average_win_pct),
            bounce_average_loss_pct=(bounce_performance.average_loss_pct),
            bounce_profit_factor=(bounce_performance.profit_factor),
            bounce_compounded_return_pct=(bounce_performance.compounded_return_pct),
            bounce_average_holding_days=(bounce_performance.average_holding_days),
            bounce_average_mfe_pct=(bounce_performance.average_mfe_pct),
            bounce_average_mae_pct=(bounce_performance.average_mae_pct),
            bounce_peak_giveback_pct=(bounce_performance.average_peak_giveback_pct),
            total_return_pct=(result.portfolio.total_return_pct),
            cagr_pct=(result.portfolio_metrics.cagr_pct),
            max_drawdown_pct=(result.portfolio_metrics.max_drawdown_pct),
            sharpe_ratio=(result.portfolio_metrics.sharpe_ratio),
            profit_factor=(result.metrics.profit_factor),
            win_rate_pct=(result.metrics.win_rate_pct),
            average_trade_pct=(result.metrics.average_return_pct),
            average_win_pct=(result.metrics.average_win_pct),
            average_loss_pct=(result.metrics.average_loss_pct),
            completed_trades=(result.metrics.total_trades),
            exposure_pct=(result.portfolio_metrics.exposure_pct),
            average_holding_days=(result.portfolio_metrics.average_holding_days),
            average_mfe_pct=(result.diagnostics.average_mfe_pct),
            average_mae_pct=(result.diagnostics.average_mae_pct),
            peak_giveback_pct=(result.diagnostics.average_peak_giveback_pct),
            stock_buy_hold_return_pct=(result.buy_and_hold.total_return_pct),
            spy_buy_hold_return_pct=(result.spy_buy_and_hold.total_return_pct),
        )


def _median_values(
    values: list[Decimal],
) -> Decimal | None:
    if not values:
        return None

    return median(values)


def _metric_values(
    rows: list[StrategyUniverseRow],
    attribute: str,
) -> list[Decimal]:
    values: list[Decimal] = []

    for row in rows:
        value = getattr(
            row,
            attribute,
        )

        if isinstance(
            value,
            Decimal,
        ):
            values.append(value)

    return values


def _format_decimal(
    value: Decimal | None,
    *,
    suffix: str = "%",
) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}{suffix}"


def build_strategy_universe_summary(
    rows: list[StrategyUniverseRow],
    *,
    strategy_name: StrategyName,
    start: date,
    end: date,
) -> str:
    successful = [row for row in rows if row.status == "ok"]

    failed = [row for row in rows if row.status != "ok"]

    profitable = sum(
        1 for row in successful if (row.total_return_pct is not None and row.total_return_pct > 0)
    )

    beats_spy = sum(
        1
        for row in successful
        if (
            row.total_return_pct is not None
            and row.spy_buy_hold_return_pct is not None
            and row.total_return_pct > row.spy_buy_hold_return_pct
        )
    )

    beats_stock = sum(
        1
        for row in successful
        if (
            row.total_return_pct is not None
            and row.stock_buy_hold_return_pct is not None
            and row.total_return_pct > row.stock_buy_hold_return_pct
        )
    )

    no_trade_count = sum(1 for row in successful if row.completed_trades == 0)

    median_return = _median_values(
        _metric_values(
            successful,
            "total_return_pct",
        )
    )

    median_cagr = _median_values(
        _metric_values(
            successful,
            "cagr_pct",
        )
    )

    median_drawdown = _median_values(
        _metric_values(
            successful,
            "max_drawdown_pct",
        )
    )

    median_sharpe = _median_values(
        _metric_values(
            successful,
            "sharpe_ratio",
        )
    )

    median_profit_factor = _median_values(
        _metric_values(
            successful,
            "profit_factor",
        )
    )

    median_win_rate = _median_values(
        _metric_values(
            successful,
            "win_rate_pct",
        )
    )

    median_exposure = _median_values(
        _metric_values(
            successful,
            "exposure_pct",
        )
    )

    median_holding = _median_values(
        _metric_values(
            successful,
            "average_holding_days",
        )
    )

    median_mfe = _median_values(
        _metric_values(
            successful,
            "average_mfe_pct",
        )
    )

    median_mae = _median_values(
        _metric_values(
            successful,
            "average_mae_pct",
        )
    )

    median_giveback = _median_values(
        _metric_values(
            successful,
            "peak_giveback_pct",
        )
    )

    ranked = sorted(
        (row for row in successful if row.total_return_pct is not None),
        key=lambda row: (
            row.total_return_pct if row.total_return_pct is not None else Decimal("-Infinity")
        ),
        reverse=True,
    )

    top = ranked[:10]
    bottom = ranked[-10:]

    total_breakouts = sum(row.breakout_buy_signals or 0 for row in successful)

    total_bounces = sum(row.bounce_buy_signals or 0 for row in successful)

    metadata_lines: list[str] = []

    metadata_row = successful[0] if successful else rows[0] if rows else None

    if strategy_name == StrategyName.EMA20_PULLBACK:
        exit_mode = metadata_row.exit_mode if metadata_row is not None else None

        metadata_lines.append(f"Exit mode: {exit_mode or 'N/A'}")

        if exit_mode == TrendExitMode.HYBRID.value and metadata_row is not None:
            threshold = metadata_row.hybrid_trend_threshold_pct

            metadata_lines.append(f"Hybrid trend threshold: {_format_decimal(threshold)}")

    if strategy_name == StrategyName.MICHO_150:
        micho_entry_mode = metadata_row.micho_entry_mode if metadata_row is not None else None

        metadata_lines.append(f"Micho entry mode: {micho_entry_mode or 'N/A'}")

    lines = [
        "=" * 72,
        "AlphaPilot Strategy Universe Backtest",
        "=" * 72,
        f"Strategy: {strategy_name.value}",
        *metadata_lines,
        f"Period: {start} -> {end}",
        ("Universe: current active S&P 500 constituents (^GSPC)"),
        "",
        "METHODOLOGY NOTE",
        "----------------",
        ("This uses the CURRENT S&P 500 constituent list and therefore has survivorship bias."),
        "",
        f"Rows processed: {len(rows)}",
        f"Successful: {len(successful)}",
        f"Failed: {len(failed)}",
        "",
        "UNIVERSE RESULTS",
        "----------------",
        (f"Profitable stocks: {profitable}/{len(successful)}"),
        (f"Beats SPY: {beats_spy}/{len(successful)}"),
        (f"Beats own-stock Buy & Hold: {beats_stock}/{len(successful)}"),
        (f"No completed trades: {no_trade_count}/{len(successful)}"),
        "",
        "MEDIAN METRICS",
        "--------------",
        (f"Total return: {_format_decimal(median_return)}"),
        (f"CAGR: {_format_decimal(median_cagr)}"),
        (f"Max drawdown: {_format_decimal(median_drawdown)}"),
        (
            "Sharpe: "
            f"{
                _format_decimal(
                    median_sharpe,
                    suffix='',
                )
            }"
        ),
        (
            "Profit factor: "
            f"{
                _format_decimal(
                    median_profit_factor,
                    suffix='',
                )
            }"
        ),
        (f"Win rate: {_format_decimal(median_win_rate)}"),
        (f"Exposure: {_format_decimal(median_exposure)}"),
        (
            "Average holding: "
            f"{
                _format_decimal(
                    median_holding,
                    suffix=' days',
                )
            }"
        ),
        (f"MFE: {_format_decimal(median_mfe)}"),
        (f"MAE: {_format_decimal(median_mae)}"),
        (f"Peak giveback: {_format_decimal(median_giveback)}"),
    ]

    if strategy_name == StrategyName.MICHO_150:
        executed_trades = sum(row.executed_trades or 0 for row in successful)

        breakout_completed_trades = sum(row.breakout_completed_trades or 0 for row in successful)

        bounce_completed_trades = sum(row.bounce_completed_trades or 0 for row in successful)

        classified_trades = breakout_completed_trades + bounce_completed_trades

        unclassified_trades = executed_trades - classified_trades

        stocks_with_breakout_trades = sum(
            1
            for row in successful
            if (row.breakout_completed_trades is not None and row.breakout_completed_trades > 0)
        )

        stocks_with_bounce_trades = sum(
            1
            for row in successful
            if (row.bounce_completed_trades is not None and row.bounce_completed_trades > 0)
        )

        breakout_median_win_rate = _median_values(
            _metric_values(
                successful,
                "breakout_win_rate_pct",
            )
        )

        breakout_median_average_trade = _median_values(
            _metric_values(
                successful,
                "breakout_average_trade_pct",
            )
        )

        breakout_median_average_win = _median_values(
            _metric_values(
                successful,
                "breakout_average_win_pct",
            )
        )

        breakout_median_average_loss = _median_values(
            _metric_values(
                successful,
                "breakout_average_loss_pct",
            )
        )

        breakout_median_profit_factor = _median_values(
            _metric_values(
                successful,
                "breakout_profit_factor",
            )
        )

        breakout_median_compounded_return = _median_values(
            _metric_values(
                successful,
                "breakout_compounded_return_pct",
            )
        )

        breakout_median_holding = _median_values(
            _metric_values(
                successful,
                "breakout_average_holding_days",
            )
        )

        breakout_median_mfe = _median_values(
            _metric_values(
                successful,
                "breakout_average_mfe_pct",
            )
        )

        breakout_median_mae = _median_values(
            _metric_values(
                successful,
                "breakout_average_mae_pct",
            )
        )

        breakout_median_giveback = _median_values(
            _metric_values(
                successful,
                "breakout_peak_giveback_pct",
            )
        )

        bounce_median_win_rate = _median_values(
            _metric_values(
                successful,
                "bounce_win_rate_pct",
            )
        )

        bounce_median_average_trade = _median_values(
            _metric_values(
                successful,
                "bounce_average_trade_pct",
            )
        )

        bounce_median_average_win = _median_values(
            _metric_values(
                successful,
                "bounce_average_win_pct",
            )
        )

        bounce_median_average_loss = _median_values(
            _metric_values(
                successful,
                "bounce_average_loss_pct",
            )
        )

        bounce_median_profit_factor = _median_values(
            _metric_values(
                successful,
                "bounce_profit_factor",
            )
        )

        bounce_median_compounded_return = _median_values(
            _metric_values(
                successful,
                "bounce_compounded_return_pct",
            )
        )

        bounce_median_holding = _median_values(
            _metric_values(
                successful,
                "bounce_average_holding_days",
            )
        )

        bounce_median_mfe = _median_values(
            _metric_values(
                successful,
                "bounce_average_mfe_pct",
            )
        )

        bounce_median_mae = _median_values(
            _metric_values(
                successful,
                "bounce_average_mae_pct",
            )
        )

        bounce_median_giveback = _median_values(
            _metric_values(
                successful,
                "bounce_peak_giveback_pct",
            )
        )

        breakout_head_to_head_wins = 0
        bounce_head_to_head_wins = 0
        head_to_head_ties = 0
        head_to_head_compared = 0

        for row in successful:
            breakout_average_trade = row.breakout_average_trade_pct

            bounce_average_trade = row.bounce_average_trade_pct

            if breakout_average_trade is None or bounce_average_trade is None:
                continue

            head_to_head_compared += 1

            if breakout_average_trade > bounce_average_trade:
                breakout_head_to_head_wins += 1

            elif bounce_average_trade > breakout_average_trade:
                bounce_head_to_head_wins += 1

            else:
                head_to_head_ties += 1

        lines.extend(
            [
                "",
                "MICHO ENTRY SIGNALS",
                "-------------------",
                (f"MA150 breakout signals: {total_breakouts}"),
                (f"MA150 bounce signals: {total_bounces}"),
                "",
                "MICHO EXECUTED ENTRY ANALYSIS",
                "-----------------------------",
                (f"Total completed trades: {executed_trades}"),
                (f"Classified completed trades: {classified_trades}"),
                (f"Unclassified completed trades: {unclassified_trades}"),
                "",
                "BREAKOUT",
                "--------",
                (f"Completed trades: {breakout_completed_trades}"),
                (f"Stocks with completed trades: {stocks_with_breakout_trades}/{len(successful)}"),
                (f"Median win rate: {_format_decimal(breakout_median_win_rate)}"),
                (f"Median average trade: {_format_decimal(breakout_median_average_trade)}"),
                (f"Median average win: {_format_decimal(breakout_median_average_win)}"),
                (f"Median average loss: {_format_decimal(breakout_median_average_loss)}"),
                (
                    "Median profit factor: "
                    f"{
                        _format_decimal(
                            breakout_median_profit_factor,
                            suffix='',
                        )
                    }"
                ),
                (f"Median compounded return: {_format_decimal(breakout_median_compounded_return)}"),
                (
                    "Median holding: "
                    f"{
                        _format_decimal(
                            breakout_median_holding,
                            suffix=' days',
                        )
                    }"
                ),
                (f"Median MFE: {_format_decimal(breakout_median_mfe)}"),
                (f"Median MAE: {_format_decimal(breakout_median_mae)}"),
                (f"Median peak giveback: {_format_decimal(breakout_median_giveback)}"),
                "",
                "BOUNCE",
                "------",
                (f"Completed trades: {bounce_completed_trades}"),
                (f"Stocks with completed trades: {stocks_with_bounce_trades}/{len(successful)}"),
                (f"Median win rate: {_format_decimal(bounce_median_win_rate)}"),
                (f"Median average trade: {_format_decimal(bounce_median_average_trade)}"),
                (f"Median average win: {_format_decimal(bounce_median_average_win)}"),
                (f"Median average loss: {_format_decimal(bounce_median_average_loss)}"),
                (
                    "Median profit factor: "
                    f"{
                        _format_decimal(
                            bounce_median_profit_factor,
                            suffix='',
                        )
                    }"
                ),
                (f"Median compounded return: {_format_decimal(bounce_median_compounded_return)}"),
                (
                    "Median holding: "
                    f"{
                        _format_decimal(
                            bounce_median_holding,
                            suffix=' days',
                        )
                    }"
                ),
                (f"Median MFE: {_format_decimal(bounce_median_mfe)}"),
                (f"Median MAE: {_format_decimal(bounce_median_mae)}"),
                (f"Median peak giveback: {_format_decimal(bounce_median_giveback)}"),
                "",
                "HEAD TO HEAD",
                "------------",
                (f"Stocks compared: {head_to_head_compared}"),
                (f"Breakout higher average trade: {breakout_head_to_head_wins}"),
                (f"Bounce higher average trade: {bounce_head_to_head_wins}"),
                (f"Ties: {head_to_head_ties}"),
            ]
        )

    lines.extend(
        [
            "",
            "TOP 10 TOTAL RETURNS",
            "--------------------",
        ]
    )

    lines.extend(
        (f"{row.ticker}: {row.total_return_pct:.2f}%")
        for row in top
        if row.total_return_pct is not None
    )

    lines.extend(
        [
            "",
            "BOTTOM 10 TOTAL RETURNS",
            "-----------------------",
        ]
    )

    lines.extend(
        (f"{row.ticker}: {row.total_return_pct:.2f}%")
        for row in bottom
        if row.total_return_pct is not None
    )

    if failed:
        lines.extend(
            [
                "",
                "FAILED TICKERS",
                "--------------",
            ]
        )

        lines.extend((f"{row.ticker}: {row.error}") for row in failed)

    lines.extend(
        [
            "",
            "=" * 72,
        ]
    )

    return "\n".join(lines)
