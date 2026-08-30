from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    ClassificationGates,
    DatasetBinding,
    ParameterDeclaration,
    ResearchPeriod,
    StrategyLabProtocol,
    StrategySpecification,
    TemporalFold,
)

SNAPSHOT_ID = UUID("5dd60f87-8947-4850-ba87-4a7df655528c")
DATASET_SHA256 = "b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b"
UNIVERSE_SHA256 = "369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8"


@dataclass(frozen=True, slots=True)
class RelativeStopMetrics:
    cagr_retention_pct: Decimal
    drawdown_worsening_pp: Decimal
    sharpe_retention_pct: Decimal
    calmar_retention_pct: Decimal
    turnover_increase_pct: Decimal
    tail_loss_improvement_pct: Decimal
    top5_concentration_worsening_pp: Decimal = Decimal("0")
    folds_return_better_or_equal: int = 0
    folds_sharpe_better_or_equal: int = 0
    folds_drawdown_better_or_equal: int = 0
    recovery_within_20_sessions_pct: Decimal = Decimal("0")


def passes_development_gates(metrics: RelativeStopMetrics) -> bool:
    return (
        metrics.cagr_retention_pct >= Decimal("75")
        and metrics.drawdown_worsening_pp <= Decimal("1.5")
        and metrics.sharpe_retention_pct >= Decimal("80")
        and metrics.calmar_retention_pct >= Decimal("80")
        and metrics.turnover_increase_pct <= Decimal("25")
        and metrics.tail_loss_improvement_pct >= Decimal("10")
    )


def passes_validation_gates(metrics: RelativeStopMetrics) -> bool:
    return (
        metrics.cagr_retention_pct >= Decimal("70")
        and metrics.drawdown_worsening_pp <= Decimal("1.5")
        and metrics.sharpe_retention_pct >= Decimal("80")
        and metrics.calmar_retention_pct >= Decimal("80")
        and metrics.top5_concentration_worsening_pp <= Decimal("5")
        and metrics.turnover_increase_pct <= Decimal("25")
        and metrics.folds_return_better_or_equal >= 2
        and metrics.folds_sharpe_better_or_equal >= 2
        and metrics.folds_drawdown_better_or_equal >= 2
        and metrics.recovery_within_20_sessions_pct <= Decimal("65")
    )


def build_stop_protocol(strategy: StrategyName) -> StrategyLabProtocol:
    values = (
        ("control", "atr-stop-2-0", "atr-stop-2-5", "atr-stop-3-0")
        if strategy == StrategyName.EMA20_PULLBACK
        else ("control", "atr-stop-1-0", "atr-stop-1-5", "atr-stop-2-0", "atr-stop-2-5")
    )
    sizing = (
        "equal-slot" if strategy == StrategyName.EMA20_PULLBACK else "atr-volatility-normalized"
    )
    candidates = tuple(
        CandidateConfiguration(
            label=value,
            parameter_values=(("protective_stop", value),),
            selection_policy="relative-strength-20",
            sizing_policy=sizing,
            cost_scenario=CostScenarioName.COST_LOW,
        )
        for value in values
    )
    return StrategyLabProtocol(
        protocol_version=1,
        specification=StrategySpecification(
            strategy_key=strategy.value,
            strategy_version=1,
            display_name=f"{strategy.value} Sprint 20 governed stop research",
            description="Closed static ATR14 protective-stop candidate study; control included.",
            entry_configuration=(("frozen_strategy_rules", True),),
            exit_configuration=(("strategy_exit_remains_active", True),),
            required_lookback_bars=150 if strategy == StrategyName.MICHO_150 else 50,
            allowed_selection_policies=("relative-strength-20",),
            allowed_sizing_policies=(sizing,),
            parameters=(ParameterDeclaration("protective_stop", values),),
            research_notes=("No trailing or profit-management candidates are reopened.",),
        ),
        dataset=DatasetBinding(SNAPSHOT_ID, DATASET_SHA256, UNIVERSE_SHA256),
        development_period=ResearchPeriod(date(2021, 8, 20), date(2024, 12, 31)),
        validation_period=ResearchPeriod(date(2025, 1, 1), date(2026, 8, 20)),
        folds=(
            TemporalFold("fold-1", ResearchPeriod(date(2021, 8, 20), date(2022, 12, 31))),
            TemporalFold("fold-2", ResearchPeriod(date(2023, 1, 1), date(2024, 12, 31))),
            TemporalFold("fold-3", ResearchPeriod(date(2025, 1, 1), date(2026, 8, 20))),
        ),
        candidates=candidates,
        gates=ClassificationGates(),
        limitations=(
            "Survivorship bias from the current-constituent universe.",
            "Daily OHLC cannot establish the ordering of multiple intraday thresholds.",
            "COST_LOW is a fixed 5 bps-per-side friction assumption.",
        ),
    )


def build_round2_ema_protocol() -> StrategyLabProtocol:
    """Frozen, closed Round 2 structural candidate protocol."""
    base = build_stop_protocol(StrategyName.EMA20_PULLBACK)
    values = ("control", "atr-stop-2-0", "signal-day-low-invalidation")
    return StrategyLabProtocol(
        protocol_version=2,
        specification=StrategySpecification(
            strategy_key=StrategyName.EMA20_PULLBACK.value,
            strategy_version=1,
            display_name="EMA Sprint 20 Round 2 governed loss-control research",
            description="Closed signal-candle structural invalidation study.",
            entry_configuration=(("frozen_strategy_rules", True),),
            exit_configuration=(("strategy_exit_remains_active", True),),
            required_lookback_bars=50,
            allowed_selection_policies=("relative-strength-20",),
            allowed_sizing_policies=("equal-slot",),
            parameters=(ParameterDeclaration("protective_stop", values),),
            research_notes=("No grid, trailing stop, or profit target is permitted.",),
        ),
        dataset=base.dataset,
        development_period=base.development_period,
        validation_period=base.validation_period,
        folds=base.folds,
        candidates=tuple(
            CandidateConfiguration(
                label=value,
                parameter_values=(("protective_stop", value),),
                selection_policy="relative-strength-20",
                sizing_policy="equal-slot",
                cost_scenario=CostScenarioName.COST_LOW,
            )
            for value in values
        ),
        gates=base.gates,
        limitations=base.limitations,
    )
