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

from alphapilot.backtesting.candidate_selection import (
    SelectionPolicyName,
    create_selection_policy,
)
from alphapilot.backtesting.cost_scenarios import CostScenarioName, get_cost_scenario
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import (
    MultiPortfolioBacktestService,
    MultiPortfolioRunResult,
)
from alphapilot.database.session import get_db
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import SizingPolicyName
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
        "--cost-scenario",
        choices=[item.value for item in CostScenarioName],
        default=None,
        help="Named Sprint 9 cost scenario; overrides commission/slippage when set.",
    )
    parser.add_argument("--fold-label", default="full-period")
    parser.add_argument(
        "--sizing-policy",
        choices=[item.value for item in SizingPolicyName],
        default=SizingPolicyName.EQUAL_SLOT.value,
    )
    parser.add_argument("--risk-per-position-pct", type=Decimal, default=Decimal("1"))
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--atr-stop-multiple", type=Decimal, default=Decimal("2"))
    parser.add_argument("--max-position-weight-pct", type=Decimal, default=Decimal("10"))
    parser.add_argument("--max-portfolio-risk-pct", type=Decimal, default=Decimal("8"))
    parser.add_argument("--minimum-cash-reserve-pct", type=Decimal, default=Decimal("10"))
    parser.add_argument("--max-sector-weight-pct", type=Decimal, default=Decimal("30"))
    parser.add_argument(
        "--selection-policy",
        choices=[item.value for item in SelectionPolicyName],
        default=SelectionPolicyName.TICKER_ASCENDING.value,
    )
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
    cost_scenario: str = "custom",
    fold_label: str = "full-period",
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
            (
                "Sizing method: fixed equal slot (current equity / max positions)"
                if config.sizing_policy == SizingPolicyName.EQUAL_SLOT
                else (
                    "Sizing method: 1% equity risk / (2 x ATR14), capped by constraints"
                    if config.sizing_policy == SizingPolicyName.ATR_RISK
                    else "Sizing method: candidate-batch inverse ATR percentage weights"
                )
            ),
            f"Sizing policy: {config.sizing_policy.value}",
            f"Commission per order: ${config.commission_per_order:.2f}",
            f"Slippage: {config.slippage_bps:.2f} bps",
            f"Cost scenario: {cost_scenario}",
            f"Temporal fold: {fold_label}",
            f"Selection policy: {result.selection_policy_name}",
            f"Risk per position: {config.risk_config.risk_per_position_pct:.2f}%",
            f"ATR period: {config.risk_config.atr_period}",
            f"ATR stop multiple: {config.risk_config.atr_stop_multiple:.2f}",
            f"Max position weight: {config.risk_config.max_position_weight_pct:.2f}%",
            f"Max portfolio risk: {config.risk_config.max_portfolio_risk_pct:.2f}%",
            f"Minimum cash reserve: {config.risk_config.minimum_cash_reserve_pct:.2f}%",
            f"Max sector weight: {config.risk_config.max_sector_weight_pct:.2f}%",
            (
                "Ranking formula: stock 20-bar return minus SPY 20-bar return; "
                "signal-day information only."
                if result.selection_policy_name == SelectionPolicyName.RELATIVE_STRENGTH_20.value
                else "Selection warning: stable ticker ordering is a non-alpha control."
            ),
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
            f"BUY approved: {result.portfolio.risk_diagnostics.buy_approved}",
            f"BUY skipped: {result.portfolio.risk_diagnostics.buy_skipped}",
            f"Skips by reason: {dict(result.portfolio.risk_diagnostics.skips_by_reason)}",
            "Average proposed position weight: "
            f"{_format_decimal(result.portfolio.risk_diagnostics.average_position_weight_pct)}",
            "Average modeled position risk: "
            f"${result.portfolio.risk_diagnostics.average_modeled_position_risk:.2f}",
            f"Average cash reserve: ${result.portfolio.risk_diagnostics.average_cash_reserve:.2f}",
            "Average portfolio modeled risk: "
            f"${result.portfolio.risk_diagnostics.average_portfolio_modeled_risk:.2f}",
            "Max portfolio modeled risk: "
            f"${result.portfolio.risk_diagnostics.max_portfolio_modeled_risk:.2f}",
            "Average portfolio modeled risk percent: "
            f"{_format_decimal(result.portfolio.risk_diagnostics.average_portfolio_modeled_risk_pct)}",
            "Max portfolio modeled risk percent: "
            f"{_format_decimal(result.portfolio.risk_diagnostics.max_portfolio_modeled_risk_pct)}",
            f"Average cash: ${result.portfolio.risk_diagnostics.average_cash:.2f}",
            "Average cash percent: "
            f"{_format_decimal(result.portfolio.risk_diagnostics.average_cash_pct)}",
            f"Final cash: ${result.portfolio.risk_diagnostics.final_cash:.2f}",
            "Max sector weight observed: "
            f"{_format_decimal(result.portfolio.risk_diagnostics.max_sector_weight_observed_pct)}",
            "",
            "RETURN ATTRIBUTION",
            "------------------",
            f"Gross realized P&L: ${result.attribution.gross_realized_pnl:.2f}",
            f"Gross unrealized P&L: ${result.attribution.gross_unrealized_pnl:.2f}",
            f"Transaction friction: ${result.attribution.transaction_friction:.2f}",
            f"Net realized P&L: ${result.attribution.realized_pnl:.2f}",
            f"Net unrealized P&L: ${result.attribution.unrealized_pnl:.2f}",
            f"Combined P&L: ${result.attribution.total_pnl:.2f}",
            f"Reconciliation residual: ${result.attribution.reconciliation_residual:.8f}",
            f"Unique tickers held: {result.attribution.unique_tickers_held}",
            f"Positive contributors: {result.attribution.positive_tickers}",
            f"Negative contributors: {result.attribution.negative_tickers}",
            f"Top 1 P&L: ${result.attribution.top_1_pnl:.2f}",
            f"Top 5 P&L: ${result.attribution.top_5_pnl:.2f}",
            f"Top 10 P&L: ${result.attribution.top_10_pnl:.2f}",
            "Top 1 share of portfolio gain: "
            f"{_format_decimal(result.attribution.top_1_gain_share_pct)}",
            "Top 5 share of portfolio gain: "
            f"{_format_decimal(result.attribution.top_5_gain_share_pct)}",
            "Top 10 share of portfolio gain: "
            f"{_format_decimal(result.attribution.top_10_gain_share_pct)}",
            "Top 1 share of positive P&L: "
            f"{_format_decimal(result.attribution.top_1_positive_pnl_share_pct)}",
            "Top 5 share of positive P&L: "
            f"{_format_decimal(result.attribution.top_5_positive_pnl_share_pct)}",
            f"Positive-P&L HHI: {_format_decimal(result.attribution.positive_pnl_hhi, '')}",
            "",
            "RANKING DIAGNOSTICS",
            "-------------------",
            (
                "BUY candidates considered: "
                f"{result.portfolio.ranking_diagnostics.total_candidates_considered}"
            ),
            (f"Selected candidates: {result.portfolio.ranking_diagnostics.selected_candidates}"),
            (f"Rejected candidates: {result.portfolio.ranking_diagnostics.rejected_candidates}"),
            (
                "Candidate selection rate: "
                f"{_format_decimal(result.portfolio.ranking_diagnostics.selection_rate_pct)}"
            ),
            (
                "Constrained candidate days: "
                f"{result.portfolio.ranking_diagnostics.constrained_days}"
            ),
            (
                "Rejected because slots full: "
                f"{result.portfolio.ranking_diagnostics.rejected_slots_full}"
            ),
            (
                "Rejected because allocation could not buy one share: "
                f"{result.portfolio.ranking_diagnostics.rejected_insufficient_allocation}"
            ),
            (
                "Average selected RS20 score: "
                f"{_format_decimal(_score_pct(result.portfolio.ranking_diagnostics.average_selected_score))}"
            ),
            (
                "Average rejected RS20 score: "
                f"{_format_decimal(_score_pct(result.portfolio.ranking_diagnostics.average_rejected_score))}"
            ),
            (
                "Candidates lacking ranking history: "
                f"{result.portfolio.ranking_diagnostics.missing_score_candidates}"
            ),
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
    selection_policy: SelectionPolicyName,
    cost_scenario: str,
    fold_label: str,
    sizing_policy: SizingPolicyName,
) -> str:
    suffix = strategy_name.value.replace("-", "_")

    if strategy_name == StrategyName.EMA20_PULLBACK:
        suffix += f"_{exit_mode.value.replace('-', '_')}"

        if exit_mode == TrendExitMode.HYBRID:
            suffix += f"_{str(hybrid_threshold).replace('.', '_')}pct"
    else:
        suffix += f"_{micho_entry_mode.value.replace('-', '_')}"

    safe_policy = selection_policy.value.replace("-", "_")
    safe_cost = cost_scenario.replace("-", "_")
    safe_fold = fold_label.replace("-", "_")
    safe_sizing = sizing_policy.value.replace("-", "_")
    return (
        f"multi_portfolio_{suffix}_{safe_policy}_{safe_sizing}_{safe_cost}_"
        f"{safe_fold}_{start}_{end}"
    )


def _score_pct(value: Decimal | None) -> Decimal | None:
    return value * Decimal("100") if value is not None else None


async def run(args: argparse.Namespace) -> None:
    strategy_name = StrategyName(args.strategy)
    exit_mode = TrendExitMode(args.exit_mode)
    micho_entry_mode = MichoEntryMode(args.micho_entry_mode)
    selection_policy_name = SelectionPolicyName(args.selection_policy)
    scenario_name = CostScenarioName(args.cost_scenario) if args.cost_scenario is not None else None
    scenario = get_cost_scenario(scenario_name) if scenario_name is not None else None
    sizing_policy = SizingPolicyName(args.sizing_policy)
    risk_config = PortfolioRiskConfig(
        risk_per_position_pct=args.risk_per_position_pct,
        atr_period=args.atr_period,
        atr_stop_multiple=args.atr_stop_multiple,
        max_position_weight_pct=args.max_position_weight_pct,
        max_portfolio_risk_pct=args.max_portfolio_risk_pct,
        minimum_cash_reserve_pct=args.minimum_cash_reserve_pct,
        max_sector_weight_pct=args.max_sector_weight_pct,
        max_positions=args.max_positions,
    )
    config = MultiPortfolioConfig(
        initial_capital=args.capital,
        max_positions=args.max_positions,
        commission_per_order=(scenario.commission_per_order if scenario else args.commission),
        slippage_bps=(scenario.slippage_bps if scenario else args.slippage_bps),
        sizing_policy=sizing_policy,
        risk_config=risk_config,
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
            selection_policy=create_selection_policy(selection_policy_name),
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
            selection_policy_name,
            scenario.name.value if scenario else "custom",
            args.fold_label,
            sizing_policy,
        )
        summary_path = args.output_dir / f"{base_name}_summary.txt"
        equity_path = args.output_dir / f"{base_name}_equity.csv"
        trades_path = args.output_dir / f"{base_name}_trades.csv"
        audit_path = args.output_dir / f"{base_name}_selection_audit.csv"
        attribution_path = args.output_dir / f"{base_name}_attribution.csv"
        sector_path = args.output_dir / f"{base_name}_sector_attribution.csv"
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
                cost_scenario=scenario.name.value if scenario else "custom",
                fold_label=args.fold_label,
            ),
            encoding="utf-8",
        )

        with equity_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(
                [
                    "trading_day",
                    "cash",
                    "invested_value",
                    "equity",
                    "open_positions",
                    "modeled_portfolio_risk",
                    "cash_reserve",
                    "max_sector_weight_pct",
                ]
            )

            for point in result.portfolio.equity_curve:
                writer.writerow(
                    [
                        point.trading_day,
                        point.cash,
                        point.invested_value,
                        point.equity,
                        point.open_positions,
                        point.modeled_portfolio_risk,
                        point.cash_reserve,
                        point.max_sector_weight_pct,
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

        with audit_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(
                [
                    "execution_day",
                    "signal_day",
                    "ticker",
                    "selection_policy",
                    "ranking_score",
                    "candidate_rank",
                    "selected",
                    "rejection_reason",
                    "available_slots",
                    "cash",
                    "equity",
                    "decision_reason",
                    "proposed_shares",
                    "target_allocation",
                    "target_weight_pct",
                    "modeled_position_risk",
                    "portfolio_risk_before",
                    "sector_weight_before_pct",
                    "sector_weight_after_pct",
                    "normalized_sizing_weight",
                ]
            )

            for item in result.portfolio.selection_audit:
                writer.writerow(
                    [
                        item.execution_day,
                        item.signal_day,
                        item.ticker,
                        item.selection_policy,
                        item.ranking_score,
                        item.candidate_rank,
                        item.selected,
                        item.rejection_reason,
                        item.available_slots,
                        item.cash,
                        item.equity,
                        item.decision_reason,
                        item.proposed_shares,
                        item.target_allocation,
                        item.target_weight_pct,
                        item.modeled_position_risk,
                        item.portfolio_risk_before,
                        item.sector_weight_before_pct,
                        item.sector_weight_after_pct,
                        item.normalized_sizing_weight,
                    ]
                )

        with attribution_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(
                [
                    "ticker",
                    "sector",
                    "completed_trades",
                    "open_positions",
                    "gross_realized_pnl",
                    "gross_unrealized_pnl",
                    "transaction_friction",
                    "realized_pnl",
                    "unrealized_pnl",
                    "total_pnl",
                    "contribution_pct",
                ]
            )
            for attribution_item in result.attribution.tickers:
                writer.writerow(
                    [
                        attribution_item.ticker,
                        attribution_item.sector,
                        attribution_item.completed_trades,
                        attribution_item.open_positions,
                        attribution_item.gross_realized_pnl,
                        attribution_item.gross_unrealized_pnl,
                        attribution_item.transaction_friction,
                        attribution_item.realized_pnl,
                        attribution_item.unrealized_pnl,
                        attribution_item.total_pnl,
                        attribution_item.contribution_pct,
                    ]
                )

        with sector_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(
                [
                    "sector",
                    "unique_tickers",
                    "completed_trades",
                    "realized_pnl",
                    "unrealized_pnl",
                    "total_pnl",
                    "contribution_pct",
                ]
            )
            for sector_item in result.attribution.sectors:
                writer.writerow(
                    [
                        sector_item.sector,
                        sector_item.unique_tickers,
                        sector_item.completed_trades,
                        sector_item.realized_pnl,
                        sector_item.unrealized_pnl,
                        sector_item.total_pnl,
                        sector_item.contribution_pct,
                    ]
                )

        print(summary_path.read_text(encoding="utf-8"))
        print(f"Summary: {summary_path}")
        print(f"Equity:  {equity_path}")
        print(f"Trades:  {trades_path}")
        print(f"Audit:   {audit_path}")
        print(f"Attribution: {attribution_path}")
        print(f"Sectors:     {sector_path}")
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
