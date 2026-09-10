from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    ParameterDeclaration,
    StrategyLabProtocol,
    StrategySpecification,
)
from alphapilot.strategy_lab.sprint20_stop_protocol import build_stop_protocol


@dataclass(slots=True, frozen=True)
class Ema20LossControlGateMetrics:
    cagr_retention_pct: Decimal
    drawdown_worsening_pp: Decimal
    sharpe_retention_pct: Decimal
    calmar_retention_pct: Decimal
    turnover_increase_pct: Decimal
    tail_loss_improvement_pct: Decimal
    boundary_coverage_pct: Decimal
    risk_distance_p90_pct: Decimal
    risk_distance_max_pct: Decimal
    top5_concentration_worsening_pp: Decimal = Decimal("0")
    folds_return_better_or_equal: int = 0
    folds_sharpe_better_or_equal: int = 0
    folds_drawdown_better_or_equal: int = 0
    recovery_within_20_sessions_pct: Decimal = Decimal("0")


def passes_development_gates(metrics: Ema20LossControlGateMetrics) -> bool:
    return (
        metrics.cagr_retention_pct >= Decimal("75")
        and metrics.drawdown_worsening_pp <= Decimal("1.5")
        and metrics.sharpe_retention_pct >= Decimal("80")
        and metrics.calmar_retention_pct >= Decimal("80")
        and metrics.turnover_increase_pct <= Decimal("25")
        and metrics.tail_loss_improvement_pct >= Decimal("10")
        and metrics.boundary_coverage_pct == Decimal("100")
        and metrics.risk_distance_p90_pct <= Decimal("10")
        and metrics.risk_distance_max_pct <= Decimal("20")
    )


def passes_validation_gates(metrics: Ema20LossControlGateMetrics) -> bool:
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
        and metrics.boundary_coverage_pct == Decimal("100")
        and metrics.risk_distance_p90_pct <= Decimal("10")
        and metrics.risk_distance_max_pct <= Decimal("20")
    )


def build_ema20_loss_control_protocol() -> StrategyLabProtocol:
    """Return the closed protocol frozen before the focused research run."""

    prior = build_stop_protocol(StrategyName.EMA20_PULLBACK)
    values = (
        "control",
        "fixed-signal-ema50-stop",
        "atr-stop-2-0-reused-sprint20",
    )
    return StrategyLabProtocol(
        protocol_version=3,
        specification=StrategySpecification(
            strategy_key=StrategyName.EMA20_PULLBACK.value,
            strategy_version=1,
            display_name="EMA20 pre-entry numeric loss-control research",
            description=(
                "One new fixed signal-day EMA50 protective boundary plus exact reused "
                "Sprint 20 ATR14 2x evidence."
            ),
            entry_configuration=(
                ("frozen_strategy_rules", True),
                ("ema20_entry_safety_upper_pct", Decimal("1")),
            ),
            exit_configuration=(
                ("strategy_exit", "HYBRID_2_PERCENT"),
                ("fixed_ema50_trigger", "DAILY_LOW_OR_GAP_OPEN"),
                ("new_boundary_activates_session_after_entry", True),
            ),
            required_lookback_bars=50,
            allowed_selection_policies=("relative-strength-20",),
            allowed_sizing_policies=("equal-slot",),
            parameters=(ParameterDeclaration("loss_control_policy", values),),
            research_notes=(
                "ATR period is fixed at 14 and K at 2.0 for reused evidence.",
                "No third policy, grid search, trailing stop, or profit target is permitted.",
                "A passing candidate requires independent human review before integration.",
            ),
        ),
        dataset=prior.dataset,
        development_period=prior.development_period,
        validation_period=prior.validation_period,
        folds=prior.folds,
        candidates=tuple(
            CandidateConfiguration(
                label=value,
                parameter_values=(("loss_control_policy", value),),
                selection_policy="relative-strength-20",
                sizing_policy="equal-slot",
                cost_scenario=CostScenarioName.COST_LOW,
            )
            for value in values
        ),
        gates=prior.gates,
        limitations=(
            *prior.limitations,
            "All development, validation, and fold periods were previously observed.",
            "A numeric boundary cannot guarantee its fill price during a gap.",
            "Final open positions are marked to market rather than force-liquidated.",
        ),
    )
