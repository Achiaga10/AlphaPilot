from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from alphapilot.backtesting.cost_scenarios import CostScenarioName
from alphapilot.strategy.achia_ema20 import AchiaStratEMA20Strategy
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
    StrategyLabResultSummary,
    StrategySpecification,
    TemporalFold,
)
from alphapilot.strategy_lab.sprint20_stop_protocol import (
    DATASET_SHA256,
    SNAPSHOT_ID,
    UNIVERSE_SHA256,
)


def build_achia_protocol() -> StrategyLabProtocol:
    """Research profile only: deliberately absent from operational StrategyProfile registry."""
    return StrategyLabProtocol(
        protocol_version=1,
        specification=StrategySpecification(
            strategy_key=AchiaStratEMA20Strategy.STRATEGY_ID,
            strategy_version=1,
            display_name=AchiaStratEMA20Strategy.DISPLAY_NAME,
            description=(
                "LONG_ONLY; one fixed EMA20/EMA50 zone-entry hypothesis with native loss control."
            ),
            entry_configuration=(
                ("ema_fast", 20),
                ("ema_slow", 50),
                ("ema_seed", "SMA_THEN_ALPHA_2_OVER_N_PLUS_1"),
                ("entry_lower_multiplier", Decimal("0.90")),
                ("entry_upper_multiplier", Decimal("1.01")),
                ("trend", "EMA20_STRICTLY_GREATER_THAN_EMA50"),
                ("entry_price", "NEXT_TICKER_OPEN_PLUS_BUY_SLIPPAGE"),
                ("independent_entry_and_held_exit_facts", True),
                ("stock_warmup_calendar_days", 120),
                ("spy_warmup_calendar_days", 400),
                ("market_filter", "NONE"),
                ("signal_low_requirement", "NONE"),
                ("initial_capital", Decimal("100000")),
                ("max_positions", 10),
                ("sizing", "EXISTING_EQUAL_SLOT_WHOLE_SHARES"),
                ("signal_level_analysis", "INDEPENDENT_TICKER_ONE_SLOT_NO_RS20"),
                ("ranking", "PORTFOLIO_ONLY_SIGNAL_DAY_RS20"),
            ),
            exit_configuration=(
                ("atr_period", 14),
                ("atr_method", "SIMPLE_MEAN_14_TRUE_RANGES"),
                ("entry_percent_stop_component", Decimal("0.01")),
                ("stop", "ENTRY_FILL_MINUS_SIGNAL_ATR14_MINUS_1PCT_ENTRY_FILL"),
                ("policy_version", "achia-ema20-atr14-plus-1pct-stop-v1"),
                ("static", True),
                ("entry_session_active", True),
                ("gap_trigger", "OPEN_LE_STOP_RAW_EXIT_OPEN"),
                ("intraday_trigger", "LOW_LE_STOP_RAW_EXIT_STOP"),
                ("strategy_exit", "COMPLETED_CLOSE_STRICTLY_BELOW_EMA20_NEXT_OPEN"),
                (
                    "precedence",
                    "OPEN_GAP_STOP_THEN_PENDING_EXIT_THEN_INTRADAY_STOP_THEN_CLOSE_SIGNAL",
                ),
                ("no_recycle_while_held_buy", True),
                ("final_open", "MARK_TO_CLOSE"),
                ("mfe_mae", "EXIT_DAY_CENSORED_PRE_EXIT_OBSERVED_RANGE"),
                ("post_stop_recovery", "5_10_20_TICKER_CLOSES_WITHIN_PERIOD_20_SESSION_CENSORING"),
            ),
            required_lookback_bars=50,
            allowed_selection_policies=("relative-strength-20",),
            allowed_sizing_policies=("equal-slot",),
            parameters=(),
            research_notes=(
                "No parameter search; unchanged EMA20 Pullback HYBRID 2% "
                "is descriptive reference only.",
                "Both main and pooled-independent-ticker evidence required; "
                "pooled CAGR is undefined.",
                "Entry-location buckets [-10,-7.5),[-7.5,-5),[-5,-2.5),[-2.5,0),[0,1].",
                "Stop-risk buckets (0,2],(2,4],(4,6],(6,10],>10 are descriptive, never tuned.",
                "Development and validation: net return/CAGR >0, completed >=100, "
                "Sharpe/Calmar >=0.50, PF >1.",
                "Pooled independent net expectancy >0, valid boundary coverage 100%, "
                "risk P90 <=10%, max <=20%.",
                "Preparation failures block advancement; "
                "insufficient histories are counted explicitly.",
                "Any failed development gate rejects before validation; "
                "failed validation rejects before folds.",
                "Validation additionally DD <=30%; >=2 positive folds required, "
                "all3 required for PROMISING.",
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
                label="achia-v1",
                parameter_values=(),
                selection_policy="relative-strength-20",
                sizing_policy="equal-slot",
                cost_scenario=CostScenarioName.COST_LOW,
            ),
        ),
        gates=ClassificationGates(
            maximum_validation_drawdown_pct=Decimal("30"),
            minimum_validation_sharpe=Decimal("0.50"),
            minimum_validation_calmar=Decimal("0.50"),
            minimum_folds_beating_reference=2,
        ),
        limitations=(
            "Survivorship bias: frozen current constituents, not point-in-time membership.",
            "LEGACY_PARTIAL candle provenance and split-adjusted price-return SPY benchmark, "
            "not dividend total return.",
            "Previously observed development/validation/folds, not pristine future OOS.",
            "Fixed 5 bps per side, zero commission; "
            "no liquidity/capacity model or guaranteed stop fill.",
            "Daily OHLC cannot identify pre-stop high; exit-day excursions are censored.",
            "Final positions marked to market, never force-liquidated; no operational activation.",
        ),
    )


@dataclass(frozen=True, slots=True)
class AchiaGateEvidence:
    result: StrategyLabResultSummary
    pooled_expectancy_pct: Decimal | None
    boundary_coverage_pct: Decimal
    risk_p90_pct: Decimal | None
    risk_max_pct: Decimal | None
    failed_tickers: int


def failed_achia_gates(evidence: AchiaGateEvidence, *, validation: bool = False) -> tuple[str, ...]:
    result = evidence.result
    checks = {
        "positive net return": result.total_return_pct > 0,
        "positive CAGR": result.cagr_pct is not None and result.cagr_pct > 0,
        "at least 100 completed trades": result.completed_trades >= 100,
        "Sharpe >= 0.50": result.sharpe_ratio is not None and result.sharpe_ratio >= Decimal("0.5"),
        "Calmar >= 0.50": result.calmar_ratio is not None and result.calmar_ratio >= Decimal("0.5"),
        "profit factor > 1": result.profit_factor is not None and result.profit_factor > 1,
        "positive pooled independent expectancy": evidence.pooled_expectancy_pct is not None
        and evidence.pooled_expectancy_pct > 0,
        "100% valid native boundary/provenance": evidence.boundary_coverage_pct == 100,
        "stop risk P90 <= 10%": evidence.risk_p90_pct is not None and evidence.risk_p90_pct <= 10,
        "stop risk maximum <= 20%": evidence.risk_max_pct is not None
        and evidence.risk_max_pct <= 20,
        "no unexplained failed tickers": evidence.failed_tickers == 0,
    }
    if validation:
        checks["validation drawdown <= 30%"] = result.max_drawdown_pct <= 30
    return tuple(name for name, passed in checks.items() if not passed)


def reject_achia_stage(
    experiment: StrategyLabExperiment, reasons: tuple[str, ...]
) -> StrategyLabExperiment:
    """Terminal negative evidence, never a shortcut to a positive Lab classification."""
    if experiment.stage not in (ExperimentStage.DEVELOPMENT, ExperimentStage.VALIDATION):
        raise ValueError("early rejection requires development or validation evidence")
    if not reasons or not experiment.development_evidence:
        raise ValueError("early rejection requires explicit failing evidence and reasons")
    if experiment.stage == ExperimentStage.VALIDATION and experiment.validation_evidence is None:
        raise ValueError("validation rejection requires validation evidence")
    return replace(
        experiment,
        stage=ExperimentStage.CLASSIFIED,
        classification=ClassificationDecision(
            ExperimentClassification.REJECTED,
            reasons,
            experiment.protocol.limitations,
        ),
        profile_candidate=None,
    )
