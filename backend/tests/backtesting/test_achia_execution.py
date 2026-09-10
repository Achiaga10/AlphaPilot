"""Native Achia execution semantics, isolated from historical stop conventions."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.backtesting.trade_management import (
    ConfiguredTradeManagementPolicy,
    ProtectiveStopPolicyName,
    TradeManagementConfig,
    TradeManagementExitReason,
)
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal

START = date(2024, 1, 2)
MANAGEMENT = TradeManagementConfig(
    protective_stop=ProtectiveStopPolicyName.ACHIA_ATR_PLUS_ENTRY_PERCENT
)


def bar(
    offset: int,
    *,
    buy: bool = False,
    exit_signal: bool = False,
    open_price: str = "100",
    low: str = "99",
    high: str = "101",
    close: str = "100",
) -> BacktestBarResult:
    return BacktestBarResult(
        trading_day=START + timedelta(days=offset),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        evaluation=StrategyEvaluation(
            signal=Signal.BUY if buy else Signal.HOLD,
            reason=SignalReason.ACHIA_EMA20_ENTRY_ZONE
            if buy
            else SignalReason.ACHIA_EMA20_NO_ENTRY,
            ema20=Decimal("100"),
            ema50=Decimal("90"),
            position_exit_reason=SignalReason.CLOSE_BELOW_EMA20 if exit_signal else None,
        ),
    )


def run(*bars: BacktestBarResult, atr: Decimal | None = Decimal("3"), bps: str = "0"):
    config = MultiPortfolioConfig(
        initial_capital=Decimal("10000"),
        max_positions=1,
        slippage_bps=Decimal(bps),
        trade_management=MANAGEMENT,
    )
    return MultiPortfolioSimulator(config).run(
        {"AAA": BacktestResult("AAA", bars[0].trading_day, bars[-1].trading_day, bars)},
        atr_values={
            ("AAA", row.trading_day): atr if index == 0 else Decimal("60")
            for index, row in enumerate(bars)
        },
    )


def test_native_stop_formula_is_atr_plus_one_percent_not_atr_times_101() -> None:
    policy = ConfiguredTradeManagementPolicy(MANAGEMENT)
    assert policy.initial_stop(entry_price=Decimal("100"), atr=Decimal("3")) == Decimal("96")
    assert MANAGEMENT.stop_active_on_entry_session
    assert MANAGEMENT.protective_stop.policy_version == "achia-ema20-atr14-plus-1pct-stop-v1"


def test_native_boundary_audit_uses_exact_execution_order_for_repeating_atr() -> None:
    from alphapilot.backtesting.achia_reporting import entry_rows

    result = run(
        bar(0, buy=True),
        bar(1, open_price="105.295", low="104", high="106", close="105"),
        atr=Decimal("5.232135714285714285714285714"),
        bps="5",
    )
    row = entry_rows(result)[0]
    fill, atr, stop = row["entry_fill"], row["signal_atr14"], row["stop_price"]
    assert stop == fill - atr - fill * Decimal("0.01")
    assert stop != fill * Decimal("0.99") - atr
    assert abs(stop - (fill * Decimal("0.99") - atr)) < Decimal("1e-24")
    assert row["valid_native_boundary"] is True


@pytest.mark.parametrize("atr", [None, Decimal("0"), Decimal("-1"), Decimal("100"), Decimal("NaN")])
def test_missing_or_invalid_atr_or_stop_rejects_entry(atr: Decimal | None) -> None:
    result = run(bar(0, buy=True), bar(1), atr=atr)
    assert not result.trades and not result.open_positions
    assert result.final_equity == result.initial_capital
    assert not result.selection_audit[0].selected


@pytest.mark.parametrize("low,stopped", [("95", True), ("96", True), ("96.01", False)])
def test_stop_activates_on_entry_day_and_touch_is_inclusive(low: str, stopped: bool) -> None:
    result = run(bar(0, buy=True), bar(1, low=low, exit_signal=True))
    assert bool(result.trades) == stopped
    if stopped:
        assert result.trades[0].entry_day == result.trades[0].exit_day
        assert result.trades[0].exit_reference_price == 96
        assert result.trades[0].exit_reason == TradeManagementExitReason.PROTECTIVE_STOP


def test_entry_fill_stop_provenance_and_cost_reconciliation() -> None:
    result = run(bar(0, buy=True), bar(1, low="95"), bps="5")
    trade = result.trades[0]
    assert trade.entry_price == Decimal("100.05")
    assert trade.initial_atr == Decimal("3")
    assert trade.initial_stop == Decimal("96.0495")
    assert trade.exit_price == Decimal("96.0495") * Decimal("0.9995")
    assert trade.loss_control_as_of == START
    assert trade.loss_control_source == "SIGNAL_DAY_ATR14"
    assert trade.loss_control_policy_version == MANAGEMENT.protective_stop.policy_version
    assert PortfolioAttributionCalculator().calculate(result).reconciliation_residual == 0


def test_gap_exit_has_priority_over_pending_strategy_exit_and_no_double_exit() -> None:
    result = run(
        bar(0, buy=True),
        bar(1, exit_signal=True),
        bar(2, open_price="90", high="95", low="80"),
        bar(3),
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_reference_price == 90
    assert result.trades[0].gap_through_stop
    assert result.trades[0].exit_reason == TradeManagementExitReason.PROTECTIVE_STOP


def test_completed_close_exit_executes_at_next_available_open_not_future_low() -> None:
    result = run(
        bar(0, buy=True),
        bar(1, exit_signal=True, close="99"),
        bar(5, open_price="98", low="60", high="110"),
    )
    trade = result.trades[0]
    assert trade.exit_reference_price == 98
    assert trade.exit_day == START + timedelta(days=5)
    assert trade.exit_signal_day == START + timedelta(days=1)
    assert trade.strategy_exit_reason == SignalReason.CLOSE_BELOW_EMA20


def test_same_day_intraday_stop_precedes_later_close_exit() -> None:
    result = run(
        bar(0, buy=True),
        bar(1),
        bar(2, low="95", close="97", exit_signal=True),
        bar(3, open_price="90", low="85"),
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_day == START + timedelta(days=2)
    assert result.trades[0].exit_reason == TradeManagementExitReason.PROTECTIVE_STOP


def test_stop_does_not_move_with_future_atr_or_ema() -> None:
    result = run(
        bar(0, buy=True),
        bar(1),
        replace(
            bar(2, low="97"),
            evaluation=StrategyEvaluation(
                Signal.HOLD, SignalReason.ACHIA_EMA20_NO_ENTRY, ema20=Decimal("999")
            ),
        ),
    )
    assert result.trades == ()
    assert result.open_positions[0].initial_stop == result.open_positions[0].effective_stop == 96


def test_overlapping_buy_and_exit_facts_do_not_erase_entry_or_rebuy_on_exit_open() -> None:
    result = run(bar(0, buy=True, exit_signal=True), bar(1, buy=True, exit_signal=True), bar(2))
    assert len(result.trades) == 1
    assert result.trades[0].entry_signal_day == START
    assert result.trades[0].exit_day == START + timedelta(days=2)
    assert not result.open_positions
    assert len(result.selection_audit) == 1


def test_gap_stop_cannot_recycle_a_buy_signal_generated_while_held() -> None:
    result = run(
        bar(0, buy=True), bar(1, buy=True), bar(2, open_price="90", low="85", buy=True), bar(3)
    )
    assert len(result.trades) == 1
    assert len(result.open_positions) == 1
    assert result.open_positions[0].entry_signal_day == START + timedelta(days=2)
    assert result.open_positions[0].entry_day == START + timedelta(days=3)


def test_no_last_day_entry_or_exit_fill_is_fabricated() -> None:
    assert run(bar(0, buy=True)).open_positions == ()
    result = run(bar(0, buy=True), bar(1, exit_signal=True))
    assert result.trades == () and len(result.open_positions) == 1


def test_future_high_close_do_not_change_entry_price_or_initial_stop() -> None:
    baseline = run(bar(0, buy=True), bar(1))
    changed = run(bar(0, buy=True), bar(1, high="500", close="300"))
    assert baseline.open_positions[0].entry_price == changed.open_positions[0].entry_price == 100
    assert baseline.open_positions[0].initial_stop == changed.open_positions[0].initial_stop == 96


def test_identical_inputs_are_reproducible_and_native_stop_does_not_change_old_activation() -> None:
    bars = (bar(0, buy=True), bar(1, low="95"))
    assert run(*bars) == run(*bars)
    assert not TradeManagementConfig(
        protective_stop=ProtectiveStopPolicyName.ATR_STOP_2_0
    ).stop_active_on_entry_session


def test_ranked_shared_cash_and_slots_cannot_reuse_later_intraday_stop_proceeds() -> None:
    from alphapilot.backtesting.candidate_selection import RelativeStrength20SelectionPolicy

    bars = (bar(0, buy=True), bar(1, low="95"))
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("10000"),
            max_positions=1,
            slippage_bps=Decimal("5"),
            trade_management=MANAGEMENT,
        ),
        selection_policy=RelativeStrength20SelectionPolicy(),
    ).run(
        {
            ticker: BacktestResult(ticker, START, bars[-1].trading_day, bars)
            for ticker in ("AAA", "ZZZ")
        },
        atr_values={(ticker, START): Decimal("3") for ticker in ("AAA", "ZZZ")},
        ranking_scores={("AAA", START): Decimal("0.1"), ("ZZZ", START): Decimal("0.2")},
    )
    assert len(result.trades) == 1 and result.trades[0].ticker == "ZZZ"
    assert not result.open_positions
    assert [item.selected for item in result.selection_audit] == [True, False]
    assert all(point.cash >= 0 for point in result.equity_curve)
    assert result.trades[0].shares == 99
