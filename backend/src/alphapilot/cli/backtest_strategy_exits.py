from __future__ import annotations

import argparse
import asyncio
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
from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioBacktestService
from alphapilot.backtesting.sprint12_diagnostics import (
    calculate_universe_exit_comparisons,
    write_universe_exit_comparisons,
)
from alphapilot.backtesting.sprint12_protocol import (
    Sprint12ExitConfiguration,
    Sprint12ResearchStage,
    default_sizing_policy_value,
    validate_stage_configurations,
)
from alphapilot.backtesting.sprint12_reporting import (
    build_metadata,
    write_sprint12_report,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen Sprint 12 strategy-exit research matrix."
    )
    parser.add_argument("--strategy", choices=[item.value for item in StrategyName], required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--stage",
        choices=[item.value for item in Sprint12ResearchStage],
        required=True,
    )
    parser.add_argument("--fold-label", default="full-period")
    parser.add_argument(
        "--configuration",
        action="append",
        required=True,
        help=(
            "Repeat for each run: control, atr-stop-1-5, atr-stop-2-0, atr-stop-3-0, "
            "or one stop plus one declared trailing/profit overlay joined by '+'."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest_reports/sprint12"),
    )
    return parser


def parse_configurations(values: list[str]) -> tuple[Sprint12ExitConfiguration, ...]:
    return tuple(Sprint12ExitConfiguration.parse(value) for value in values)


def build_portfolio_config(
    strategy: StrategyName,
    exit_configuration: Sprint12ExitConfiguration,
) -> MultiPortfolioConfig:
    scenario = get_cost_scenario(CostScenarioName.COST_LOW)
    sizing = SizingPolicyName(default_sizing_policy_value(strategy))
    return MultiPortfolioConfig(
        initial_capital=Decimal("100000"),
        max_positions=10,
        commission_per_order=scenario.commission_per_order,
        slippage_bps=scenario.slippage_bps,
        sizing_policy=sizing,
        risk_config=PortfolioRiskConfig(
            risk_per_position_pct=Decimal("1"),
            atr_period=14,
            atr_stop_multiple=Decimal("2"),
            max_position_weight_pct=Decimal("10"),
            max_portfolio_risk_pct=Decimal("8"),
            minimum_cash_reserve_pct=Decimal("10"),
            max_sector_weight_pct=Decimal("30"),
            max_positions=10,
        ),
        trade_management=exit_configuration.trade_management,
    )


def entry_configuration(strategy: StrategyName) -> str:
    if strategy == StrategyName.EMA20_PULLBACK:
        return "EMA20 Pullback; HYBRID exit; frozen 2% trend threshold"
    return "Micho V1; BOTH entry mode; SMA150/trend-breakdown strategy exit"


async def run(args: argparse.Namespace) -> None:
    strategy_name = StrategyName(args.strategy)
    stage = Sprint12ResearchStage(args.stage)
    configurations = parse_configurations(args.configuration)
    validate_stage_configurations(
        stage=stage,
        strategy=strategy_name,
        configurations=configurations,
    )
    strategy = create_strategy(
        strategy_name,
        exit_mode=TrendExitMode.HYBRID,
        hybrid_trend_threshold_pct=Decimal("2"),
        micho_entry_mode=MichoEntryMode.BOTH,
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
            selection_policy=create_selection_policy(SelectionPolicyName.RELATIVE_STRENGTH_20),
        )
        prepared = await service.prepare(start=args.start, end=args.end)
        matrix_configs = tuple(
            (configuration.label, build_portfolio_config(strategy_name, configuration))
            for configuration in configurations
        )
        for exit_configuration in configurations:
            config = dict(matrix_configs)[exit_configuration.label]
            result = service.run_prepared(prepared, config=config)
            metadata = build_metadata(
                result=result,
                strategy=strategy_name,
                entry_configuration=entry_configuration(strategy_name),
                config=config,
                exit_configuration=exit_configuration,
                stage=stage,
                fold_label=args.fold_label,
                start=args.start,
                end=args.end,
            )
            base_name = "_".join(
                (
                    strategy_name.value.replace("-", "_"),
                    args.fold_label.replace("-", "_"),
                    exit_configuration.label.replace("-", "_").replace("+", "__"),
                    str(args.start),
                    str(args.end),
                )
            )
            paths = write_sprint12_report(
                args.output_dir / stage.value,
                base_name,
                result=result,
                metadata=metadata,
            )
            metrics = result.metrics
            print(
                f"{strategy_name.value} {exit_configuration.label}: "
                f"return={metrics.total_return_pct:.2f}% "
                f"CAGR={metrics.cagr_pct if metrics.cagr_pct is not None else 'N/A'} "
                f"DD={metrics.max_drawdown_pct:.2f}% "
                f"Sharpe={metrics.sharpe_ratio if metrics.sharpe_ratio is not None else 'N/A'} "
                f"Calmar={metrics.calmar_ratio if metrics.calmar_ratio is not None else 'N/A'}"
            )
            print(f"Summary: {paths[0]}")
        universe_rows = calculate_universe_exit_comparisons(
            prepared=prepared,
            selection_policy=service.selection_policy,
            configurations=matrix_configs,
        )
        if universe_rows:
            universe_path = (
                args.output_dir
                / stage.value
                / (
                    f"{strategy_name.value.replace('-', '_')}_{args.fold_label.replace('-', '_')}_"
                    f"{args.start}_{args.end}_universe_comparison.csv"
                )
            )
            write_universe_exit_comparisons(universe_path, universe_rows)
            print(f"Universe diagnostics: {universe_path}")
    finally:
        await db_generator.aclose()


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


def main() -> None:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    args = build_parser().parse_args()
    asyncio.run(run(args), loop_factory=create_event_loop)


if __name__ == "__main__":
    main()
