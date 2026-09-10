"""Single frozen research candidate; no production StrategyProfile registration."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    ClassificationDecision,
    ClassificationGates,
    DatasetBinding,
    ExperimentClassification,
    ExperimentStage,
    ResearchPeriod,
    StrategyLabExperiment,
    StrategyLabProtocol,
    StrategySpecification,
    TemporalFold,
)
from alphapilot.strategy_lab.sprint20_stop_protocol import (
    DATASET_SHA256,
    SNAPSHOT_ID,
    UNIVERSE_SHA256,
)


def build_shauli_protocol() -> StrategyLabProtocol:
    return StrategyLabProtocol(
        protocol_version=1,
        specification=StrategySpecification(
            strategy_key="shauli-strat-v1",
            strategy_version=1,
            display_name="Shauli_strat",
            description="SHAULI_STRAT DAILY V1; LONG_ONLY research interpretation, not intraday",
            entry_configuration=(
                ("timeframe", "1Day"),
                ("direction", "LONG_ONLY"),
                ("swing_left", 2),
                ("swing_right", 2),
                ("pivots", "STRICT_CONFIRMED_AT_I_PLUS_2"),
                ("equal_high_low_liquidity", False),
                ("structure", "LATEST_CONFIRMED_HH_AND_HL"),
                ("bos", "COMPLETED_CLOSE_GT_PREVIOUSLY_CONFIRMED_HIGH"),
                ("inducement", "CONFIRMED_UNBREACHED_POST_BOS_HIGHER_LOW"),
                ("sweep", "SAME_CANDLE_LOW_LT_SSLQ_CLOSE_GT_SSLQ"),
                ("confirmation", "POST_SWEEP_CLOSE_GT_FROZEN_PRE_SWEEP_HIGH"),
                ("displacement", "POST_SWEEP_THREE_BARS_BULLISH_MIDDLE_CLOSE_BREAK_AND_FVG"),
                ("fvg", "LOW_C_GT_HIGH_A_POSITIVE_WIDTH_ONLY"),
                ("ob", "LAST_BEARISH_SWEEP_INCLUSIVE_TO_MIDDLE_EXCLUSIVE_FULL_WICKS_OPTIONAL"),
                ("poi", "POSITIVE_OB_FVG_INTERSECTION_ELSE_FVG"),
                ("entry", "LATER_SESSION_POI_MIDPOINT_LIMIT_NO_FAVORABLE_OPEN_IMPROVEMENT"),
                ("discount", "POI_MIDPOINT_LE_SWEEP_TO_FVG_RANGE_MIDPOINT"),
                ("initial_rr", Decimal("2.0")),
                ("initial_capital", Decimal("100000")),
                ("max_positions", 10),
                ("news", "NONE"),
                ("warmup", "ALL_PRIOR_SNAPSHOT_BARS"),
                ("ranking", "LAST_COMPLETED_SESSION_RS20_PORTFOLIO_ONLY"),
                ("capital_reservation", "RANKED_PRIOR_TO_INTRADAY_PATH_OBSERVATION"),
                ("setup_expiry", "NO_TIMEOUT_INVALID_STRUCTURE_STOP_OR_CONSUMED_TARGET"),
            ),
            exit_configuration=(
                ("stop", "MIN_SWEEP_LOW_AND_OPTIONAL_OB_LOW"),
                ("stop_buffer", "NONE"),
                ("target", "NEAREST_UNCONSUMED_CONFIRMED_HIGH_ABOVE_ACTUAL_FILL"),
                ("liquidity_consumption", "HIGH_GE_TARGET"),
                ("static_stop_target", True),
                ("entry_stop", "ENTRY_THEN_STOP"),
                ("ambiguous_stop_target", "STOP_FIRST"),
                ("opening_precedence", True),
                (
                    "entry_target_no_stop_open_between",
                    "AMBIGUOUS_ENTRY_TARGET_ORDER_CANCEL_NO_TRADE",
                ),
                ("partial_breakeven_trailing_time_exit", "NONE"),
                ("final_open", "MARK_TO_MARKET_NOT_FORCE_CLOSED"),
                ("reentry", "NEW_FULL_SEQUENCE_AFTER_EXIT"),
            ),
            required_lookback_bars=5,
            allowed_selection_policies=("relative-strength-20",),
            allowed_sizing_policies=("equal-slot",),
            parameters=(),
            research_notes=(
                "Source SHA256 ffb0a09aee2d8ca22edcd31d2b9f04fb906cdcf257975add483e8918a5313792",
                "User subsequently approved the entry-target-only ambiguity exclusion exactly.",
                "Development and validation: >=100 completed, positive return/CAGR/independent "
                "expectancy, Sharpe/Calmar >=0.50, PF >1, 100% stop/target provenance, "
                "risk P90<=10%, max<=20%, cash>=0, positions<=10, reconciliation<=1e-8 dollars, "
                "verified dataset, no unexplained preparation failures.",
                "Failure closes subsequent stages. No parameters searched or retuned.",
                "All historical periods already observed; no future-OOS claim.",
                "No-trade ambiguity percentages use unique ready setups and would-be trigger bars.",
            ),
        ),
        dataset=DatasetBinding(SNAPSHOT_ID, DATASET_SHA256, UNIVERSE_SHA256),
        development_period=ResearchPeriod(date(2021, 8, 20), date(2024, 12, 31)),
        validation_period=ResearchPeriod(date(2025, 1, 1), date(2026, 8, 20)),
        folds=(
            TemporalFold("fold-1", ResearchPeriod(date(2021, 8, 20), date(2022, 12, 31))),
            TemporalFold("fold-2", ResearchPeriod(date(2023, 1, 1), date(2024, 12, 31))),
            TemporalFold("fold-3", ResearchPeriod(date(2025, 1, 1), date(2026, 8, 20))),
        ),
        candidates=(
            CandidateConfiguration(
                "shauli-daily-v1",
                (),
                "relative-strength-20",
                "equal-slot",
                CostScenarioName.COST_LOW,
            ),
        ),
        gates=ClassificationGates(
            minimum_validation_sharpe=Decimal("0.50"),
            minimum_validation_calmar=Decimal("0.50"),
            minimum_folds_beating_reference=2,
        ),
        limitations=(
            "Survivorship bias: frozen current S&P 500 constituents, not point-in-time membership.",
            "Daily LONG_ONLY research variant cannot prove intraday source-strategy fidelity.",
            "LEGACY_PARTIAL snapshot provenance; previously observed historical periods.",
            "COST_LOW 5 bps/side, zero commission; no liquidity/capacity model or guaranteed fill.",
            "SPY price-return benchmark is not dividend total return.",
            "Final open positions marked to market; ambiguous entry/exit day excursions censored.",
            "No parameter tuning, News, operational activation, portfolio/Paper/broker writes.",
        ),
    )


def gate_checks(summary: dict[str, Any], *, verified: bool, unexplained: int) -> dict[str, bool]:
    metrics = summary["metrics"]
    risk = summary["risk_pct"]

    def minimum(name: str, floor: Decimal, *, strict: bool = False) -> bool:
        value = metrics[name]
        return value is not None and (value > floor if strict else value >= floor)

    return {
        "snapshot_hash_verified": verified,
        "completed_trades_ge_100": metrics["completed_trades"] >= 100,
        "positive_net_return": minimum("total_return_pct", Decimal(0), strict=True),
        "positive_cagr": minimum("cagr_pct", Decimal(0), strict=True),
        "sharpe_ge_0_50": minimum("sharpe_ratio", Decimal("0.50")),
        "calmar_ge_0_50": minimum("calmar_ratio", Decimal("0.50")),
        "profit_factor_gt_1": minimum("profit_factor", Decimal(1), strict=True),
        "positive_independent_expectancy": summary["independent"]["expectancy_pct"] is not None
        and summary["independent"]["expectancy_pct"] > 0,
        "valid_stop_target_provenance_100_pct": summary["valid_provenance_pct"] == 100,
        "planned_stop_p90_le_10_pct": risk["p90"] is not None and risk["p90"] <= 10,
        "planned_stop_max_le_20_pct": risk["max"] is not None and risk["max"] <= 20,
        "nonnegative_cash": summary["minimum_cash"] >= 0,
        "max_positions_respected": summary["maximum_simultaneous_positions"] <= 10,
        "accounting_reconciles": abs(summary["attribution"]["reconciliation_residual"])
        <= Decimal("1e-8"),
        "no_unexplained_preparation_failures": unexplained == 0,
    }


def reject_stage(
    experiment: StrategyLabExperiment, checks: dict[str, bool]
) -> StrategyLabExperiment:
    if experiment.stage not in (ExperimentStage.DEVELOPMENT, ExperimentStage.VALIDATION):
        raise ValueError("early rejection requires an evaluated development/validation stage")
    reasons = tuple(name for name, passed in checks.items() if not passed)
    if not reasons or not experiment.development_evidence:
        raise ValueError("early rejection requires actual failing evidence")
    if experiment.stage == ExperimentStage.VALIDATION and experiment.validation_evidence is None:
        raise ValueError("validation evidence is missing")
    return replace(
        experiment,
        stage=ExperimentStage.CLASSIFIED,
        profile_candidate=None,
        classification=ClassificationDecision(
            ExperimentClassification.REJECTED,
            reasons,
            experiment.protocol.limitations,
        ),
    )
