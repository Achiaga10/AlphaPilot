from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.sprint12_protocol import (
    Sprint12ExitConfiguration,
    Sprint12ResearchStage,
    validate_stage_configurations,
)
from alphapilot.backtesting.sprint12_reporting import (
    _portfolio_risk_pct,
    _risk_pct,
    _risk_per_share,
)
from alphapilot.backtesting.trade_management import (
    ConfiguredTradeManagementPolicy,
    ProtectiveStopPolicyName,
    TradeManagementConfig,
    TradeManagementExitReason,
)
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal
from alphapilot.strategy_lab.ema20_loss_control_protocol import (
    Ema20LossControlGateMetrics,
    build_ema20_loss_control_protocol,
    passes_development_gates,
    passes_validation_gates,
)
from alphapilot.strategy_lab.identity import experiment_identity

START = date(2025, 1, 6)


def _bar(
    offset: int,
    signal: Signal,
    *,
    open_price: str = "100",
    high: str = "101",
    low: str = "99",
    close: str = "100",
    ema50: str | None = "90",
) -> BacktestBarResult:
    reason = {
        Signal.BUY: SignalReason.EMA20_PULLBACK_RECLAIM,
        Signal.SELL: SignalReason.TREND_BREAKDOWN,
        Signal.HOLD: SignalReason.NO_PULLBACK,
    }[signal]
    return BacktestBarResult(
        trading_day=START + timedelta(days=offset),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        evaluation=StrategyEvaluation(
            signal=signal,
            reason=reason,
            ema50=Decimal(ema50) if ema50 is not None else None,
        ),
    )


def _run(*bars: BacktestBarResult):
    config = MultiPortfolioConfig(
        initial_capital=Decimal("1000"),
        max_positions=1,
        trade_management=TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.FIXED_SIGNAL_EMA50,
        ),
    )
    return MultiPortfolioSimulator(config).run(
        {
            "AAA": BacktestResult(
                ticker="AAA",
                start=bars[0].trading_day,
                end=bars[-1].trading_day,
                bars=bars,
            )
        }
    )


def test_fixed_signal_ema50_boundary_and_provenance_are_frozen_at_entry() -> None:
    result = _run(
        _bar(0, Signal.BUY, ema50="90"),
        _bar(1, Signal.HOLD, low="80", close="100", ema50="95"),
        _bar(2, Signal.HOLD, low="91", close="92", ema50="10"),
    )

    position = result.open_positions[0]
    assert position.initial_stop == Decimal("90")
    assert position.effective_stop == Decimal("90")
    assert position.loss_control_source == "SIGNAL_DAY_EMA50"
    assert position.loss_control_as_of == START
    assert position.loss_control_policy_version == "ema20-fixed-signal-ema50-stop-v1"
    assert position.entry_equity == Decimal("1000")


def test_future_ema50_cannot_change_prior_boundary_or_trigger() -> None:
    baseline = _run(
        _bar(0, Signal.BUY, ema50="90"),
        _bar(1, Signal.HOLD, ema50="90"),
        _bar(2, Signal.HOLD, low="91", ema50="89"),
    )
    changed_future = _run(
        _bar(0, Signal.BUY, ema50="90"),
        _bar(1, Signal.HOLD, ema50="999"),
        _bar(2, Signal.HOLD, low="91", ema50="9999"),
    )

    assert baseline.open_positions[0].initial_stop == Decimal("90")
    assert changed_future.open_positions[0].initial_stop == Decimal("90")
    assert baseline.trades == changed_future.trades == ()


def test_fixed_ema50_rejects_missing_nonpositive_or_nonprotective_boundary() -> None:
    policy = ConfiguredTradeManagementPolicy(
        TradeManagementConfig(protective_stop=ProtectiveStopPolicyName.FIXED_SIGNAL_EMA50)
    )

    assert policy.initial_stop(entry_price=Decimal("100"), atr=None, signal_bar_ema50=None) is None
    assert (
        policy.initial_stop(entry_price=Decimal("100"), atr=None, signal_bar_ema50=Decimal("0"))
        is None
    )
    assert (
        policy.initial_stop(entry_price=Decimal("100"), atr=None, signal_bar_ema50=Decimal("100"))
        is None
    )


def test_fixed_ema50_activates_after_entry_and_gap_fills_at_worse_open() -> None:
    result = _run(
        _bar(0, Signal.BUY, ema50="90"),
        _bar(1, Signal.HOLD, open_price="100", low="80", close="95", ema50="95"),
        _bar(2, Signal.HOLD, open_price="85", high="88", low="80", close="84", ema50="96"),
    )

    trade = result.trades[0]
    assert trade.exit_day == START + timedelta(days=2)
    assert trade.exit_reference_price == Decimal("85")
    assert trade.exit_reason == TradeManagementExitReason.FIXED_SIGNAL_EMA50_STOP
    assert trade.gap_through_stop is True
    assert trade.loss_control_as_of == START


def test_risk_per_share_percent_and_existing_equal_slot_risk_are_deterministic() -> None:
    assert _risk_per_share(Decimal("100"), Decimal("90")) == Decimal("10")
    assert _risk_pct(Decimal("100"), Decimal("90")) == Decimal("10")
    assert _portfolio_risk_pct(
        entry_price=Decimal("100"),
        boundary=Decimal("90"),
        shares=100,
        entry_equity=Decimal("100000"),
    ) == Decimal("1")
    assert _risk_per_share(Decimal("100"), None) is None
    assert _risk_pct(Decimal("100"), None) is None


def test_protocol_identity_is_closed_reproducible_and_sensitive_to_policy() -> None:
    first = build_ema20_loss_control_protocol()
    second = build_ema20_loss_control_protocol()

    assert experiment_identity(first) == experiment_identity(second)
    assert [candidate.label for candidate in first.candidates] == [
        "control",
        "fixed-signal-ema50-stop",
        "atr-stop-2-0-reused-sprint20",
    ]
    assert experiment_identity(first, first.candidates[0]) != experiment_identity(
        first, first.candidates[1]
    )


def test_new_stages_accept_only_control_then_fixed_ema50_for_ema() -> None:
    configurations = tuple(
        Sprint12ExitConfiguration.parse_ema20_loss_control(value)
        for value in ("control", "fixed-signal-ema50-stop")
    )
    validate_stage_configurations(
        stage=Sprint12ResearchStage.EMA20_LOSS_CONTROL_DEVELOPMENT,
        strategy=StrategyName.EMA20_PULLBACK,
        configurations=configurations,
    )

    with pytest.raises(ValueError, match="control followed"):
        validate_stage_configurations(
            stage=Sprint12ResearchStage.EMA20_LOSS_CONTROL_VALIDATION,
            strategy=StrategyName.EMA20_PULLBACK,
            configurations=configurations[::-1],
        )
    with pytest.raises(ValueError, match="undeclared Sprint 12 protective stop"):
        Sprint12ExitConfiguration.parse_sprint20("fixed-signal-ema50-stop")


def test_frozen_gate_functions_have_no_implicit_fallback() -> None:
    passing = Ema20LossControlGateMetrics(
        cagr_retention_pct=Decimal("75"),
        drawdown_worsening_pp=Decimal("1.5"),
        sharpe_retention_pct=Decimal("80"),
        calmar_retention_pct=Decimal("80"),
        turnover_increase_pct=Decimal("25"),
        tail_loss_improvement_pct=Decimal("10"),
        boundary_coverage_pct=Decimal("100"),
        risk_distance_p90_pct=Decimal("10"),
        risk_distance_max_pct=Decimal("20"),
        top5_concentration_worsening_pp=Decimal("5"),
        folds_return_better_or_equal=2,
        folds_sharpe_better_or_equal=2,
        folds_drawdown_better_or_equal=2,
        recovery_within_20_sessions_pct=Decimal("65"),
    )
    assert passes_development_gates(passing)
    assert passes_validation_gates(passing)
    assert not passes_development_gates(replace(passing, risk_distance_p90_pct=Decimal("10.01")))


def test_same_inputs_produce_identical_fixed_ema50_execution() -> None:
    bars = (
        _bar(0, Signal.BUY, ema50="90"),
        _bar(1, Signal.HOLD, low="99"),
        _bar(2, Signal.HOLD, low="89"),
    )
    assert _run(*bars) == _run(*bars)
