from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.backtesting.service import (
    BacktestRunResult,
    BacktestService,
)
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
class UniverseExitComparisonRow:
    ticker: str

    status: str = "ok"
    error: str = ""

    actual_start: date | None = None
    actual_end: date | None = None
    evaluated_bars: int | None = None

    ema50_total_return_pct: Decimal | None = None
    ema20_total_return_pct: Decimal | None = None

    ema50_cagr_pct: Decimal | None = None
    ema20_cagr_pct: Decimal | None = None

    ema50_max_drawdown_pct: Decimal | None = None
    ema20_max_drawdown_pct: Decimal | None = None

    ema50_sharpe_ratio: Decimal | None = None
    ema20_sharpe_ratio: Decimal | None = None

    ema50_profit_factor: Decimal | None = None
    ema20_profit_factor: Decimal | None = None

    ema50_win_rate_pct: Decimal | None = None
    ema20_win_rate_pct: Decimal | None = None

    ema50_average_trade_pct: Decimal | None = None
    ema20_average_trade_pct: Decimal | None = None

    ema50_average_win_pct: Decimal | None = None
    ema20_average_win_pct: Decimal | None = None

    ema50_average_loss_pct: Decimal | None = None
    ema20_average_loss_pct: Decimal | None = None

    ema50_completed_trades: int | None = None
    ema20_completed_trades: int | None = None

    ema50_exposure_pct: Decimal | None = None
    ema20_exposure_pct: Decimal | None = None

    ema50_average_holding_days: Decimal | None = None
    ema20_average_holding_days: Decimal | None = None

    ema50_average_mfe_pct: Decimal | None = None
    ema20_average_mfe_pct: Decimal | None = None

    ema50_average_mae_pct: Decimal | None = None
    ema20_average_mae_pct: Decimal | None = None

    ema50_peak_giveback_pct: Decimal | None = None
    ema20_peak_giveback_pct: Decimal | None = None

    stock_buy_hold_return_pct: Decimal | None = None
    spy_buy_hold_return_pct: Decimal | None = None


class UniverseExitComparisonRunner:
    """Compares EMA20 and EMA50 exits across the active S&P 500 universe."""

    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        universe_repository: IndexConstituentRepository,
    ) -> None:
        self.universe_repository = universe_repository

        self.ema50_service = BacktestService(
            company_service=company_service,
            candle_service=candle_service,
            strategy=EMA20PullbackStrategy(
                exit_mode=TrendExitMode.EMA50,
            ),
        )

        self.ema20_service = BacktestService(
            company_service=company_service,
            candle_service=candle_service,
            strategy=EMA20PullbackStrategy(
                exit_mode=TrendExitMode.EMA20,
            ),
        )

    async def list_tickers(
        self,
    ) -> list[str]:
        constituents = await self.universe_repository.list_active(
            self.SP500_INDEX_SYMBOL,
        )

        return sorted({constituent.ticker.upper() for constituent in constituents})

    async def compare_ticker(
        self,
        ticker: str,
        start: date,
        end: date,
        *,
        portfolio_config: PortfolioConfig | None = None,
    ) -> UniverseExitComparisonRow:
        ema50 = await self.ema50_service.run(
            ticker=ticker,
            start=start,
            end=end,
            portfolio_config=portfolio_config,
        )

        ema20 = await self.ema20_service.run(
            ticker=ticker,
            start=start,
            end=end,
            portfolio_config=portfolio_config,
        )

        return self._build_row(
            ticker=ticker,
            ema50=ema50,
            ema20=ema20,
        )

    @staticmethod
    def _build_row(
        *,
        ticker: str,
        ema50: BacktestRunResult,
        ema20: BacktestRunResult,
    ) -> UniverseExitComparisonRow:
        return UniverseExitComparisonRow(
            ticker=ticker,
            actual_start=ema50.backtest.start,
            actual_end=ema50.backtest.end,
            evaluated_bars=ema50.backtest.total_bars,
            ema50_total_return_pct=(ema50.portfolio.total_return_pct),
            ema20_total_return_pct=(ema20.portfolio.total_return_pct),
            ema50_cagr_pct=(ema50.portfolio_metrics.cagr_pct),
            ema20_cagr_pct=(ema20.portfolio_metrics.cagr_pct),
            ema50_max_drawdown_pct=(ema50.portfolio_metrics.max_drawdown_pct),
            ema20_max_drawdown_pct=(ema20.portfolio_metrics.max_drawdown_pct),
            ema50_sharpe_ratio=(ema50.portfolio_metrics.sharpe_ratio),
            ema20_sharpe_ratio=(ema20.portfolio_metrics.sharpe_ratio),
            ema50_profit_factor=(ema50.metrics.profit_factor),
            ema20_profit_factor=(ema20.metrics.profit_factor),
            ema50_win_rate_pct=(ema50.metrics.win_rate_pct),
            ema20_win_rate_pct=(ema20.metrics.win_rate_pct),
            ema50_average_trade_pct=(ema50.metrics.average_return_pct),
            ema20_average_trade_pct=(ema20.metrics.average_return_pct),
            ema50_average_win_pct=(ema50.metrics.average_win_pct),
            ema20_average_win_pct=(ema20.metrics.average_win_pct),
            ema50_average_loss_pct=(ema50.metrics.average_loss_pct),
            ema20_average_loss_pct=(ema20.metrics.average_loss_pct),
            ema50_completed_trades=(ema50.metrics.total_trades),
            ema20_completed_trades=(ema20.metrics.total_trades),
            ema50_exposure_pct=(ema50.portfolio_metrics.exposure_pct),
            ema20_exposure_pct=(ema20.portfolio_metrics.exposure_pct),
            ema50_average_holding_days=(ema50.portfolio_metrics.average_holding_days),
            ema20_average_holding_days=(ema20.portfolio_metrics.average_holding_days),
            ema50_average_mfe_pct=(ema50.diagnostics.average_mfe_pct),
            ema20_average_mfe_pct=(ema20.diagnostics.average_mfe_pct),
            ema50_average_mae_pct=(ema50.diagnostics.average_mae_pct),
            ema20_average_mae_pct=(ema20.diagnostics.average_mae_pct),
            ema50_peak_giveback_pct=(ema50.diagnostics.average_peak_giveback_pct),
            ema20_peak_giveback_pct=(ema20.diagnostics.average_peak_giveback_pct),
            stock_buy_hold_return_pct=(ema50.buy_and_hold.total_return_pct),
            spy_buy_hold_return_pct=(ema50.spy_buy_and_hold.total_return_pct),
        )


DecimalGetter = Callable[
    [UniverseExitComparisonRow],
    Decimal | None,
]


def _median_metric(
    rows: list[UniverseExitComparisonRow],
    getter: DecimalGetter,
) -> Decimal | None:
    values = [value for row in rows if (value := getter(row)) is not None]

    if not values:
        return None

    return median(values)


def _compare_higher(
    rows: list[UniverseExitComparisonRow],
    ema20_getter: DecimalGetter,
    ema50_getter: DecimalGetter,
) -> tuple[int, int, int]:
    ema20_wins = 0
    ema50_wins = 0
    ties = 0

    for row in rows:
        ema20 = ema20_getter(row)
        ema50 = ema50_getter(row)

        if ema20 is None or ema50 is None:
            continue

        if ema20 > ema50:
            ema20_wins += 1
        elif ema50 > ema20:
            ema50_wins += 1
        else:
            ties += 1

    return (
        ema20_wins,
        ema50_wins,
        ties,
    )


def _compare_lower(
    rows: list[UniverseExitComparisonRow],
    ema20_getter: DecimalGetter,
    ema50_getter: DecimalGetter,
) -> tuple[int, int, int]:
    ema20_wins = 0
    ema50_wins = 0
    ties = 0

    for row in rows:
        ema20 = ema20_getter(row)
        ema50 = ema50_getter(row)

        if ema20 is None or ema50 is None:
            continue

        if ema20 < ema50:
            ema20_wins += 1
        elif ema50 < ema20:
            ema50_wins += 1
        else:
            ties += 1

    return (
        ema20_wins,
        ema50_wins,
        ties,
    )


def _format_decimal(
    value: Decimal | None,
    *,
    suffix: str = "%",
) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}{suffix}"


def build_universe_summary(
    rows: list[UniverseExitComparisonRow],
    *,
    start: date,
    end: date,
) -> str:
    successful = [row for row in rows if row.status == "ok"]

    failed = [row for row in rows if row.status != "ok"]

    lines = [
        "=" * 72,
        "AlphaPilot Universe Exit Comparison",
        "=" * 72,
        f"Period: {start} -> {end}",
        "Universe: current active S&P 500 constituents (^GSPC)",
        "",
        "IMPORTANT METHODOLOGY NOTE:",
        (
            "This experiment uses the CURRENT S&P 500 constituent list. "
            "It therefore has survivorship bias and is intended primarily "
            "for EMA20-vs-EMA50 exit comparison."
        ),
        "",
        f"Rows processed: {len(rows)}",
        f"Successful: {len(successful)}",
        f"Failed: {len(failed)}",
    ]

    if not successful:
        lines.extend(
            [
                "",
                "No successful backtests.",
            ]
        )

        return "\n".join(lines)

    return_wins = _compare_higher(
        successful,
        lambda row: row.ema20_total_return_pct,
        lambda row: row.ema50_total_return_pct,
    )

    sharpe_wins = _compare_higher(
        successful,
        lambda row: row.ema20_sharpe_ratio,
        lambda row: row.ema50_sharpe_ratio,
    )

    drawdown_wins = _compare_lower(
        successful,
        lambda row: row.ema20_max_drawdown_pct,
        lambda row: row.ema50_max_drawdown_pct,
    )

    profit_factor_wins = _compare_higher(
        successful,
        lambda row: row.ema20_profit_factor,
        lambda row: row.ema50_profit_factor,
    )

    ema20_beats_spy = sum(
        1
        for row in successful
        if (
            row.ema20_total_return_pct is not None
            and row.spy_buy_hold_return_pct is not None
            and row.ema20_total_return_pct > row.spy_buy_hold_return_pct
        )
    )

    ema50_beats_spy = sum(
        1
        for row in successful
        if (
            row.ema50_total_return_pct is not None
            and row.spy_buy_hold_return_pct is not None
            and row.ema50_total_return_pct > row.spy_buy_hold_return_pct
        )
    )

    ema20_beats_stock = sum(
        1
        for row in successful
        if (
            row.ema20_total_return_pct is not None
            and row.stock_buy_hold_return_pct is not None
            and row.ema20_total_return_pct > row.stock_buy_hold_return_pct
        )
    )

    ema50_beats_stock = sum(
        1
        for row in successful
        if (
            row.ema50_total_return_pct is not None
            and row.stock_buy_hold_return_pct is not None
            and row.ema50_total_return_pct > row.stock_buy_hold_return_pct
        )
    )

    return_deltas = [
        (
            row.ticker,
            row.ema20_total_return_pct - row.ema50_total_return_pct,
        )
        for row in successful
        if (row.ema20_total_return_pct is not None and row.ema50_total_return_pct is not None)
    ]

    best_for_ema20 = sorted(
        (item for item in return_deltas if item[1] > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    best_for_ema50 = sorted(
        (item for item in return_deltas if item[1] < 0),
        key=lambda item: item[1],
    )[:10]

    ema20_median_return = _median_metric(
        successful,
        lambda row: row.ema20_total_return_pct,
    )

    ema50_median_return = _median_metric(
        successful,
        lambda row: row.ema50_total_return_pct,
    )

    ema20_median_cagr = _median_metric(
        successful,
        lambda row: row.ema20_cagr_pct,
    )

    ema50_median_cagr = _median_metric(
        successful,
        lambda row: row.ema50_cagr_pct,
    )

    ema20_median_drawdown = _median_metric(
        successful,
        lambda row: row.ema20_max_drawdown_pct,
    )

    ema50_median_drawdown = _median_metric(
        successful,
        lambda row: row.ema50_max_drawdown_pct,
    )

    ema20_median_sharpe = _median_metric(
        successful,
        lambda row: row.ema20_sharpe_ratio,
    )

    ema50_median_sharpe = _median_metric(
        successful,
        lambda row: row.ema50_sharpe_ratio,
    )

    ema20_median_giveback = _median_metric(
        successful,
        lambda row: row.ema20_peak_giveback_pct,
    )

    ema50_median_giveback = _median_metric(
        successful,
        lambda row: row.ema50_peak_giveback_pct,
    )

    lines.extend(
        [
            "",
            "EXIT MODE WINS",
            "--------------",
            (
                "Total return: "
                f"EMA20={return_wins[0]}, "
                f"EMA50={return_wins[1]}, "
                f"Ties={return_wins[2]}"
            ),
            (
                "Sharpe ratio: "
                f"EMA20={sharpe_wins[0]}, "
                f"EMA50={sharpe_wins[1]}, "
                f"Ties={sharpe_wins[2]}"
            ),
            (
                "Lower max drawdown: "
                f"EMA20={drawdown_wins[0]}, "
                f"EMA50={drawdown_wins[1]}, "
                f"Ties={drawdown_wins[2]}"
            ),
            (
                "Profit factor: "
                f"EMA20={profit_factor_wins[0]}, "
                f"EMA50={profit_factor_wins[1]}, "
                f"Ties={profit_factor_wins[2]}"
            ),
            "",
            "",
            "MEDIAN METRICS",
            "--------------",
            (
                "Total return: "
                f"EMA20={_format_decimal(ema20_median_return)}, "
                f"EMA50={_format_decimal(ema50_median_return)}"
            ),
            (
                "CAGR: "
                f"EMA20={_format_decimal(ema20_median_cagr)}, "
                f"EMA50={_format_decimal(ema50_median_cagr)}"
            ),
            (
                "Max drawdown: "
                f"EMA20={_format_decimal(ema20_median_drawdown)}, "
                f"EMA50={_format_decimal(ema50_median_drawdown)}"
            ),
            (
                "Sharpe: "
                f"EMA20={_format_decimal(ema20_median_sharpe, suffix='')}, "
                f"EMA50={_format_decimal(ema50_median_sharpe, suffix='')}"
            ),
            (
                "Peak giveback: "
                f"EMA20={_format_decimal(ema20_median_giveback)}, "
                f"EMA50={_format_decimal(ema50_median_giveback)}"
            ),
            "",
            "BENCHMARK COUNTS",
            "----------------",
            f"EMA20 beats SPY: {ema20_beats_spy}/{len(successful)}",
            f"EMA50 beats SPY: {ema50_beats_spy}/{len(successful)}",
            (f"EMA20 beats own-stock Buy & Hold: {ema20_beats_stock}/{len(successful)}"),
            (f"EMA50 beats own-stock Buy & Hold: {ema50_beats_stock}/{len(successful)}"),
            "",
            "LARGEST EMA20 RETURN IMPROVEMENTS",
            "---------------------------------",
        ]
    )

    lines.extend(f"{ticker}: {delta:+.2f} pp" for ticker, delta in best_for_ema20)

    lines.extend(
        [
            "",
            "LARGEST EMA50 RETURN ADVANTAGES",
            "-------------------------------",
        ]
    )

    lines.extend(f"{ticker}: {-delta:+.2f} pp" for ticker, delta in best_for_ema50)

    if failed:
        lines.extend(
            [
                "",
                "FAILED TICKERS",
                "--------------",
            ]
        )

        lines.extend(f"{row.ticker}: {row.error}" for row in failed)

    lines.extend(
        [
            "",
            "=" * 72,
        ]
    )

    return "\n".join(lines)
