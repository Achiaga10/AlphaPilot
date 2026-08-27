from datetime import date
from decimal import Decimal

import pytest

from alphapilot.backtesting.models import PortfolioSimulationResult
from alphapilot.backtesting.multi_portfolio_metrics import MultiPortfolioPerformanceMetrics
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioConfig,
    MultiPortfolioEquityPoint,
    MultiPortfolioSimulationResult,
)
from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioRunResult
from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.backtesting.portfolio_metrics import PortfolioPerformanceMetrics
from alphapilot.backtesting.sprint12_protocol import (
    FrozenExitSelection,
    Sprint12ExitConfiguration,
    Sprint12ResearchStage,
    validate_stage_configurations,
)
from alphapilot.backtesting.sprint12_reporting import build_metadata
from alphapilot.backtesting.trade_management import TradeManagementConfig
from alphapilot.cli.backtest_strategy_exits import build_portfolio_config
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.strategy.name import StrategyName


def test_parser_accepts_only_predeclared_stop_and_overlay_families() -> None:
    parsed = Sprint12ExitConfiguration.parse("atr-stop-2-0+atr-trailing-3-0")

    assert parsed.trade_management.protective_stop.atr_multiple == Decimal("2")
    assert parsed.trade_management.trailing_stop.atr_multiple == Decimal("3")
    with pytest.raises(ValueError, match="undeclared Sprint 12 protective"):
        Sprint12ExitConfiguration.parse("atr-stop-2-5")
    with pytest.raises(ValueError, match="undeclared Sprint 12 exit overlay"):
        Sprint12ExitConfiguration.parse("atr-stop-2-0+partial-4r")


def test_validation_and_folds_accept_only_frozen_development_selection() -> None:
    control = Sprint12ExitConfiguration.parse("control")
    protective = Sprint12ExitConfiguration.parse("atr-stop-2-0")
    final = Sprint12ExitConfiguration.parse("atr-stop-2-0+partial-2r")
    frozen = {
        StrategyName.EMA20_PULLBACK: FrozenExitSelection(
            protective=protective.trade_management,
            final=final.trade_management,
        )
    }

    validate_stage_configurations(
        stage=Sprint12ResearchStage.VALIDATION,
        strategy=StrategyName.EMA20_PULLBACK,
        configurations=(control, protective, final),
        frozen_selections=frozen,
    )
    with pytest.raises(ValueError, match="does not exactly match frozen"):
        validate_stage_configurations(
            stage=Sprint12ResearchStage.FOLD,
            strategy=StrategyName.EMA20_PULLBACK,
            configurations=(Sprint12ExitConfiguration.parse("atr-stop-3-0"),),
            frozen_selections=frozen,
        )
    with pytest.raises(ValueError, match="does not exactly match frozen"):
        validate_stage_configurations(
            stage=Sprint12ResearchStage.VALIDATION,
            strategy=StrategyName.EMA20_PULLBACK,
            configurations=(control, protective),
            frozen_selections=frozen,
        )
    with pytest.raises(ValueError, match="must be frozen"):
        validate_stage_configurations(
            stage=Sprint12ResearchStage.VALIDATION,
            strategy=StrategyName.MICHO_150,
            configurations=(control,),
            frozen_selections=frozen,
        )


def test_runner_freezes_strategy_specific_sizing_and_cost_low() -> None:
    configuration = Sprint12ExitConfiguration.parse("atr-stop-1-5")
    ema = build_portfolio_config(StrategyName.EMA20_PULLBACK, configuration)
    micho = build_portfolio_config(StrategyName.MICHO_150, configuration)

    assert ema.sizing_policy == SizingPolicyName.EQUAL_SLOT
    assert micho.sizing_policy == SizingPolicyName.ATR_VOLATILITY_NORMALIZED
    assert ema.slippage_bps == micho.slippage_bps == Decimal("5")
    assert ema.commission_per_order == micho.commission_per_order == Decimal("0")
    assert ema.max_positions == micho.max_positions == 10


def test_report_metadata_records_exact_exit_and_research_configuration() -> None:
    point = MultiPortfolioEquityPoint(
        trading_day=date(2025, 1, 2),
        cash=Decimal("100000"),
        invested_value=Decimal("0"),
        equity=Decimal("100000"),
        open_positions=0,
    )
    portfolio = MultiPortfolioSimulationResult(
        initial_capital=Decimal("100000"),
        final_equity=Decimal("100000"),
        equity_curve=(point,),
        trades=(),
        open_positions=(),
    )
    result = MultiPortfolioRunResult(
        portfolio=portfolio,
        metrics=MultiPortfolioPerformanceMetrics(
            initial_equity=Decimal("100000"),
            final_equity=Decimal("100000"),
            total_return_pct=Decimal("0"),
            cagr_pct=None,
            max_drawdown_pct=Decimal("0"),
            sharpe_ratio=None,
            exposure_pct=Decimal("0"),
            completed_trades=0,
            win_rate_pct=Decimal("0"),
            profit_factor=None,
            average_trade_pct=None,
            turnover_pct=Decimal("0"),
            average_open_positions=Decimal("0"),
            max_concurrent_positions=0,
        ),
        spy_buy_and_hold=PortfolioSimulationResult(
            ticker="SPY",
            initial_capital=Decimal("100000"),
            final_equity=Decimal("100000"),
            equity_curve=(),
            trades=(),
            open_position=None,
        ),
        spy_metrics=PortfolioPerformanceMetrics(
            final_equity=Decimal("100000"),
            total_return_pct=Decimal("0"),
            cagr_pct=None,
            max_drawdown_pct=Decimal("0"),
            sharpe_ratio=None,
            exposure_pct=Decimal("0"),
            completed_trades=0,
            average_holding_days=None,
        ),
        successful_tickers=("AAA",),
        failed_tickers=(),
        selection_policy_name="relative-strength-20",
        attribution=PortfolioAttributionCalculator().calculate(portfolio),
    )
    exit_configuration = Sprint12ExitConfiguration.parse("atr-stop-2-0+atr-trailing-3-0")
    config = MultiPortfolioConfig(trade_management=exit_configuration.trade_management)

    metadata = build_metadata(
        result=result,
        strategy=StrategyName.EMA20_PULLBACK,
        entry_configuration="EMA20 HYBRID 2%",
        config=config,
        exit_configuration=exit_configuration,
        stage=Sprint12ResearchStage.DEVELOPMENT,
        fold_label="development",
        start=date(2021, 8, 20),
        end=date(2024, 12, 31),
    )

    assert metadata.protective_stop == "atr-stop-2-0"
    assert metadata.protective_atr_multiple == Decimal("2")
    assert metadata.trailing_stop == "atr-trailing-3-0"
    assert metadata.trailing_atr_multiple == Decimal("3")
    assert metadata.atr_period == 14
    assert metadata.cost_scenario == "cost-low"
    assert metadata.data_mode == "OPERATIONAL_CURRENT"
    assert metadata.dataset_snapshot_id is None
    assert "SURVIVORSHIP BIAS" in metadata.survivorship_warning
    assert metadata.completed_session_semantics.startswith("historical completed")


def test_control_configuration_is_unchanged() -> None:
    assert Sprint12ExitConfiguration.parse("control").trade_management == TradeManagementConfig()
