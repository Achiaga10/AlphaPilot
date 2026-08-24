from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.backtesting.service import BacktestService
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.ema20_pullback import (
    EMA20PullbackStrategy,
)
from alphapilot.strategy.exit_mode import TrendExitMode


@dataclass(slots=True, frozen=True)
class HybridThresholdRow:
    ticker: str
    threshold_pct: Decimal

    status: str = "ok"
    error: str = ""

    actual_start: date | None = None
    actual_end: date | None = None
    evaluated_bars: int | None = None

    total_return_pct: Decimal | None = None
    cagr_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    sharpe_ratio: Decimal | None = None

    profit_factor: Decimal | None = None
    win_rate_pct: Decimal | None = None
    average_trade_pct: Decimal | None = None

    completed_trades: int | None = None
    exposure_pct: Decimal | None = None
    average_holding_days: Decimal | None = None

    average_mfe_pct: Decimal | None = None
    average_mae_pct: Decimal | None = None
    peak_giveback_pct: Decimal | None = None

    stock_buy_hold_return_pct: Decimal | None = None
    spy_buy_hold_return_pct: Decimal | None = None


@dataclass(slots=True, frozen=True)
class HybridThresholdAggregate:
    threshold_pct: Decimal

    successful: int
    failed: int

    profitable_count: int
    beats_spy_count: int
    beats_stock_count: int

    median_total_return_pct: Decimal | None
    median_cagr_pct: Decimal | None
    median_max_drawdown_pct: Decimal | None
    median_sharpe_ratio: Decimal | None
    median_profit_factor: Decimal | None
    median_peak_giveback_pct: Decimal | None


class HybridThresholdExperimentRunner:
    """Runs HYBRID exit thresholds across the active S&P 500 universe."""

    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        universe_repository: IndexConstituentRepository,
    ) -> None:
        self.company_service = company_service
        self.candle_service = candle_service
        self.universe_repository = universe_repository

    async def list_tickers(
        self,
    ) -> list[str]:
        constituents = await self.universe_repository.list_active(
            self.SP500_INDEX_SYMBOL,
        )

        return sorted({constituent.ticker.upper() for constituent in constituents})

    async def run_ticker(
        self,
        *,
        ticker: str,
        threshold_pct: Decimal,
        start: date,
        end: date,
        portfolio_config: PortfolioConfig,
    ) -> HybridThresholdRow:
        strategy = EMA20PullbackStrategy(
            exit_mode=TrendExitMode.HYBRID,
            hybrid_trend_threshold_pct=threshold_pct,
        )

        service = BacktestService(
            company_service=self.company_service,
            candle_service=self.candle_service,
            strategy=strategy,
        )

        result = await service.run(
            ticker=ticker,
            start=start,
            end=end,
            portfolio_config=portfolio_config,
        )

        return HybridThresholdRow(
            ticker=ticker,
            threshold_pct=threshold_pct,
            actual_start=result.backtest.start,
            actual_end=result.backtest.end,
            evaluated_bars=result.backtest.total_bars,
            total_return_pct=(result.portfolio.total_return_pct),
            cagr_pct=(result.portfolio_metrics.cagr_pct),
            max_drawdown_pct=(result.portfolio_metrics.max_drawdown_pct),
            sharpe_ratio=(result.portfolio_metrics.sharpe_ratio),
            profit_factor=(result.metrics.profit_factor),
            win_rate_pct=(result.metrics.win_rate_pct),
            average_trade_pct=(result.metrics.average_return_pct),
            completed_trades=(result.metrics.total_trades),
            exposure_pct=(result.portfolio_metrics.exposure_pct),
            average_holding_days=(result.portfolio_metrics.average_holding_days),
            average_mfe_pct=(result.diagnostics.average_mfe_pct),
            average_mae_pct=(result.diagnostics.average_mae_pct),
            peak_giveback_pct=(result.diagnostics.average_peak_giveback_pct),
            stock_buy_hold_return_pct=(result.buy_and_hold.total_return_pct),
            spy_buy_hold_return_pct=(result.spy_buy_and_hold.total_return_pct),
        )


def _median_decimal(
    values: list[Decimal],
) -> Decimal | None:
    if not values:
        return None

    return median(values)


def aggregate_thresholds(
    rows: list[HybridThresholdRow],
    thresholds: list[Decimal],
) -> list[HybridThresholdAggregate]:
    aggregates: list[HybridThresholdAggregate] = []

    for threshold in thresholds:
        threshold_rows = [row for row in rows if row.threshold_pct == threshold]

        successful = [row for row in threshold_rows if row.status == "ok"]

        failed = [row for row in threshold_rows if row.status != "ok"]

        return_values = [value for row in successful if (value := row.total_return_pct) is not None]

        cagr_values = [value for row in successful if (value := row.cagr_pct) is not None]

        drawdown_values = [
            value for row in successful if (value := row.max_drawdown_pct) is not None
        ]

        sharpe_values = [value for row in successful if (value := row.sharpe_ratio) is not None]

        profit_factor_values = [
            value for row in successful if (value := row.profit_factor) is not None
        ]

        giveback_values = [
            value for row in successful if (value := row.peak_giveback_pct) is not None
        ]

        profitable_count = sum(
            1
            for row in successful
            if (row.total_return_pct is not None and row.total_return_pct > 0)
        )

        beats_spy_count = sum(
            1
            for row in successful
            if (
                row.total_return_pct is not None
                and row.spy_buy_hold_return_pct is not None
                and row.total_return_pct > row.spy_buy_hold_return_pct
            )
        )

        beats_stock_count = sum(
            1
            for row in successful
            if (
                row.total_return_pct is not None
                and row.stock_buy_hold_return_pct is not None
                and row.total_return_pct > row.stock_buy_hold_return_pct
            )
        )

        aggregates.append(
            HybridThresholdAggregate(
                threshold_pct=threshold,
                successful=len(successful),
                failed=len(failed),
                profitable_count=profitable_count,
                beats_spy_count=beats_spy_count,
                beats_stock_count=beats_stock_count,
                median_total_return_pct=(_median_decimal(return_values)),
                median_cagr_pct=(_median_decimal(cagr_values)),
                median_max_drawdown_pct=(_median_decimal(drawdown_values)),
                median_sharpe_ratio=(_median_decimal(sharpe_values)),
                median_profit_factor=(_median_decimal(profit_factor_values)),
                median_peak_giveback_pct=(_median_decimal(giveback_values)),
            )
        )

    return aggregates


def select_threshold(
    aggregates: list[HybridThresholdAggregate],
) -> HybridThresholdAggregate:
    candidates = [
        aggregate
        for aggregate in aggregates
        if (aggregate.successful > 0 and aggregate.median_sharpe_ratio is not None)
    ]

    if not candidates:
        raise ValueError("No threshold has sufficient successful results")

    def ranking_key(
        aggregate: HybridThresholdAggregate,
    ) -> tuple[
        Decimal,
        Decimal,
        Decimal,
    ]:
        sharpe = (
            aggregate.median_sharpe_ratio
            if aggregate.median_sharpe_ratio is not None
            else Decimal("-Infinity")
        )

        drawdown = (
            aggregate.median_max_drawdown_pct
            if aggregate.median_max_drawdown_pct is not None
            else Decimal("Infinity")
        )

        total_return = (
            aggregate.median_total_return_pct
            if aggregate.median_total_return_pct is not None
            else Decimal("-Infinity")
        )

        return (
            sharpe,
            -drawdown,
            total_return,
        )

    return max(
        candidates,
        key=ranking_key,
    )


def _format_decimal(
    value: Decimal | None,
    suffix: str = "%",
) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}{suffix}"


def build_threshold_summary(
    aggregates: list[HybridThresholdAggregate],
    *,
    selected: HybridThresholdAggregate,
    start: date,
    end: date,
    universe_size: int,
) -> str:
    lines = [
        "=" * 72,
        "AlphaPilot HYBRID Threshold Development Experiment",
        "=" * 72,
        f"Period: {start} -> {end}",
        f"Universe size: {universe_size}",
        "",
        "METHODOLOGY",
        "-----------",
        ("Current S&P 500 constituents are used, so this experiment has survivorship bias."),
        ("Threshold selection rule was fixed before validation:"),
        "1. Highest median Sharpe ratio",
        "2. Lower median max drawdown",
        "3. Higher median total return",
        "",
        "THRESHOLD RESULTS",
        "-----------------",
    ]

    for aggregate in aggregates:
        lines.extend(
            [
                "",
                (f"Threshold: {aggregate.threshold_pct:.2f}%"),
                (f"  Successful: {aggregate.successful}"),
                (f"  Failed: {aggregate.failed}"),
                (f"  Median return: {_format_decimal(aggregate.median_total_return_pct)}"),
                (f"  Median CAGR: {_format_decimal(aggregate.median_cagr_pct)}"),
                (f"  Median max drawdown: {_format_decimal(aggregate.median_max_drawdown_pct)}"),
                (f"  Median Sharpe: {_format_decimal(aggregate.median_sharpe_ratio, '')}"),
                (f"  Median profit factor: {_format_decimal(aggregate.median_profit_factor, '')}"),
                (f"  Median peak giveback: {_format_decimal(aggregate.median_peak_giveback_pct)}"),
                (f"  Profitable: {aggregate.profitable_count}/{aggregate.successful}"),
                (f"  Beats SPY: {aggregate.beats_spy_count}/{aggregate.successful}"),
                (f"  Beats own stock B&H: {aggregate.beats_stock_count}/{aggregate.successful}"),
            ]
        )

    lines.extend(
        [
            "",
            "SELECTED DEVELOPMENT THRESHOLD",
            "------------------------------",
            (f"{selected.threshold_pct:.2f}%"),
            "",
            ("IMPORTANT: Do not change this threshold based on validation-period results."),
            "",
            "=" * 72,
        ]
    )

    return "\n".join(lines)
