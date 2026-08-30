from datetime import date, timedelta
from decimal import Decimal

import pytest

from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.backtesting.trade_management import (
    ConfiguredTradeManagementPolicy,
    ProfitManagementPolicyName,
    ProtectiveStopPolicyName,
    TradeManagementConfig,
    TradeManagementExitReason,
    TrailingStopPolicyName,
)
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal

START = date(2025, 1, 6)


def policy(
    stop: ProtectiveStopPolicyName = ProtectiveStopPolicyName.ATR_STOP_2_0,
    *,
    trailing: TrailingStopPolicyName = TrailingStopPolicyName.NONE,
    profit: ProfitManagementPolicyName = ProfitManagementPolicyName.NONE,
) -> ConfiguredTradeManagementPolicy:
    return ConfiguredTradeManagementPolicy(
        TradeManagementConfig(
            protective_stop=stop,
            trailing_stop=trailing,
            profit_management=profit,
        )
    )


def bar(
    offset: int,
    signal: Signal,
    *,
    open_price: str = "100",
    high: str = "101",
    low: str = "99",
    close: str = "100",
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
        evaluation=StrategyEvaluation(signal=signal, reason=reason),
    )


def run(
    *bars: BacktestBarResult,
    stop: ProtectiveStopPolicyName = ProtectiveStopPolicyName.ATR_STOP_2_0,
    trailing: TrailingStopPolicyName = TrailingStopPolicyName.NONE,
    profit: ProfitManagementPolicyName = ProfitManagementPolicyName.NONE,
    slippage_bps: str = "0",
    commission: str = "0",
    atr_values: dict[tuple[str, date], Decimal | None] | None = None,
):
    config = MultiPortfolioConfig(
        initial_capital=Decimal("1000"),
        max_positions=1,
        slippage_bps=Decimal(slippage_bps),
        commission_per_order=Decimal(commission),
        trade_management=TradeManagementConfig(
            protective_stop=stop,
            trailing_stop=trailing,
            profit_management=profit,
        ),
    )
    result = BacktestResult(
        ticker="AAA", start=bars[0].trading_day, end=bars[-1].trading_day, bars=bars
    )
    return MultiPortfolioSimulator(config).run(
        {"AAA": result},
        atr_values=atr_values or {("AAA", item.trading_day): Decimal("5") for item in bars},
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (ProtectiveStopPolicyName.ATR_STOP_1_0, Decimal("95")),
        (ProtectiveStopPolicyName.ATR_STOP_1_5, Decimal("92.5")),
        (ProtectiveStopPolicyName.ATR_STOP_2_0, Decimal("90")),
        (ProtectiveStopPolicyName.ATR_STOP_2_5, Decimal("87.5")),
        (ProtectiveStopPolicyName.ATR_STOP_3_0, Decimal("85")),
    ],
)
def test_declared_static_atr_stop_formulas(
    name: ProtectiveStopPolicyName,
    expected: Decimal,
) -> None:
    assert policy(name).initial_stop(entry_price=Decimal("100"), atr=Decimal("5")) == expected


def test_only_frozen_trade_management_configurations_are_accepted() -> None:
    with pytest.raises(ValueError, match="ATR period must be 14"):
        TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.ATR_STOP_2_0,
            atr_period=10,
        )
    with pytest.raises(ValueError, match="requires a protective ATR stop"):
        TradeManagementConfig(trailing_stop=TrailingStopPolicyName.ATR_TRAILING_2_0)
    with pytest.raises(ValueError, match="at most one additional"):
        TradeManagementConfig(
            protective_stop=ProtectiveStopPolicyName.ATR_STOP_2_0,
            trailing_stop=TrailingStopPolicyName.ATR_TRAILING_2_0,
            profit_management=ProfitManagementPolicyName.PARTIAL_2R,
        )


def test_low_crossing_stop_triggers_and_no_crossing_does_not() -> None:
    stopped = policy().evaluate(
        open_price=Decimal("95"),
        high_price=Decimal("101"),
        low_price=Decimal("89"),
        effective_stop=Decimal("90"),
        initial_stop=Decimal("90"),
        profit_target=None,
        shares=10,
        partial_profit_taken=False,
    )
    not_stopped = policy().evaluate(
        open_price=Decimal("95"),
        high_price=Decimal("101"),
        low_price=Decimal("91"),
        effective_stop=Decimal("90"),
        initial_stop=Decimal("90"),
        profit_target=None,
        shares=10,
        partial_profit_taken=False,
    )

    assert stopped is not None
    assert stopped.reference_price == Decimal("90")
    assert stopped.reason == TradeManagementExitReason.INITIAL_ATR_STOP
    assert not_stopped is None


def test_gap_below_stop_exits_at_open_then_applies_sell_slippage() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="102", low="99"),
        bar(2, Signal.HOLD, open_price="85", high="88", low="80", close="84"),
        slippage_bps="5",
    )

    trade = result.trades[0]
    assert trade.gap_through_stop is True
    assert trade.exit_reference_price == Decimal("85")
    assert trade.exit_price == Decimal("84.9575")
    assert trade.exit_reason == TradeManagementExitReason.INITIAL_ATR_STOP


def test_initial_stop_is_not_applied_on_entry_session() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="102", low="80", close="95"),
    )

    assert result.trades == ()
    assert len(result.open_positions) == 1
    assert result.open_positions[0].initial_stop == Decimal("90")


def test_strategy_exit_signal_cannot_cancel_a_stop_hit_on_its_signal_day() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99"),
        bar(2, Signal.SELL, open_price="100", high="101", low="89", close="90"),
        bar(3, Signal.HOLD, open_price="80", high="82", low="78", close="81"),
    )

    trade = result.trades[0]
    assert trade.exit_day == START + timedelta(days=2)
    assert trade.exit_price == Decimal("90")
    assert trade.exit_reason == TradeManagementExitReason.INITIAL_ATR_STOP


def test_missing_or_invalid_atr_rejects_managed_entry_without_fabricating_stop() -> None:
    bars = (bar(0, Signal.BUY), bar(1, Signal.HOLD))

    missing = run(*bars, atr_values={("AAA", START): None})
    invalid = run(*bars, atr_values={("AAA", START): Decimal("0")})

    assert missing.open_positions == ()
    assert invalid.open_positions == ()
    assert missing.trades == invalid.trades == ()


def test_trailing_stop_uses_prior_completed_close_and_atr_and_never_decreases() -> None:
    trailing = policy(trailing=TrailingStopPolicyName.ATR_TRAILING_2_0)

    first = trailing.next_effective_stop(
        initial_stop=Decimal("90"),
        previous_effective_stop=Decimal("90"),
        highest_completed_close=Decimal("110"),
        atr_through_close=Decimal("4"),
    )
    second = trailing.next_effective_stop(
        initial_stop=Decimal("90"),
        previous_effective_stop=first,
        highest_completed_close=Decimal("110"),
        atr_through_close=Decimal("8"),
    )

    assert first == Decimal("102")
    assert second == Decimal("102")


def test_current_bar_high_and_close_cannot_move_same_day_trailing_stop() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.HOLD, open_price="100", high="120", low="95", close="115"),
        bar(3, Signal.HOLD, open_price="104", high="105", low="103", close="104"),
        trailing=TrailingStopPolicyName.ATR_TRAILING_2_0,
    )

    trade = result.trades[0]
    assert trade.exit_day == START + timedelta(days=3)
    assert trade.exit_reference_price == Decimal("104")
    assert trade.gap_through_stop is True
    assert trade.exit_reason == TradeManagementExitReason.ATR_TRAILING_STOP


def test_trailing_stop_uses_atr_available_through_prior_close_only() -> None:
    bars = (
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, close="100"),
        bar(2, Signal.HOLD, open_price="100", high="110", low="99", close="108"),
        bar(3, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
    )
    result = run(
        *bars,
        trailing=TrailingStopPolicyName.ATR_TRAILING_2_0,
        atr_values={
            ("AAA", START): Decimal("5"),
            ("AAA", START + timedelta(days=1)): Decimal("5"),
            ("AAA", START + timedelta(days=2)): Decimal("2"),
            ("AAA", START + timedelta(days=3)): Decimal("50"),
        },
    )

    assert result.trades[0].exit_day == START + timedelta(days=3)
    assert result.trades[0].exit_reference_price == Decimal("100")
    assert result.trades[0].exit_reason == TradeManagementExitReason.ATR_TRAILING_STOP


def test_intraday_trailing_breach_uses_preknown_trailing_level() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.HOLD, open_price="105", high="111", low="104", close="110"),
        bar(3, Signal.HOLD, open_price="105", high="106", low="99", close="101"),
        trailing=TrailingStopPolicyName.ATR_TRAILING_2_0,
    )

    assert result.trades[0].exit_reference_price == Decimal("100")
    assert result.trades[0].gap_through_stop is False
    assert result.trades[0].exit_reason == TradeManagementExitReason.ATR_TRAILING_STOP


def test_strategy_exit_remains_active_alongside_unbreached_stop() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.SELL, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.HOLD, open_price="95", high="96", low="94", close="95"),
    )

    assert result.trades[0].exit_day == START + timedelta(days=2)
    assert result.trades[0].exit_reason == TradeManagementExitReason.STRATEGY_EXIT
    assert result.trades[0].strategy_exit_reason == SignalReason.TREND_BREAKDOWN


def test_partial_2r_uses_whole_share_floor_and_remaining_position_stays_open() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99"),
        bar(2, Signal.HOLD, open_price="110", high="121", low="95", close="115"),
        profit=ProfitManagementPolicyName.PARTIAL_2R,
    )

    trade = result.trades[0]
    assert trade.exit_reason == TradeManagementExitReason.PARTIAL_PROFIT_2R
    assert trade.exit_reference_price == Decimal("120")
    assert trade.shares == 5
    assert trade.position_closed is False
    assert result.open_positions[0].shares == 5
    assert result.open_positions[0].partial_profit_taken is True


def test_partial_2r_does_nothing_when_one_share_cannot_be_split() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="600", high="601", low="599"),
        bar(2, Signal.HOLD, open_price="610", high="621", low="600", close="615"),
        profit=ProfitManagementPolicyName.PARTIAL_2R,
    )

    assert result.trades == ()
    assert result.open_positions[0].shares == 1


def test_full_3r_gap_above_target_uses_open_and_intraday_uses_target() -> None:
    intraday = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99"),
        bar(2, Signal.HOLD, open_price="120", high="131", low="95", close="125"),
        profit=ProfitManagementPolicyName.FULL_3R,
    )
    gap = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99"),
        bar(2, Signal.HOLD, open_price="135", high="136", low="134", close="135"),
        profit=ProfitManagementPolicyName.FULL_3R,
    )

    assert intraday.trades[0].exit_reference_price == Decimal("130")
    assert gap.trades[0].exit_reference_price == Decimal("135")
    assert intraday.trades[0].exit_reason == TradeManagementExitReason.FULL_PROFIT_3R


def test_same_bar_stop_and_target_uses_conservative_stop_first() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99"),
        bar(2, Signal.HOLD, open_price="100", high="125", low="85", close="105"),
        profit=ProfitManagementPolicyName.PARTIAL_2R,
    )

    assert result.trades[0].exit_reason == TradeManagementExitReason.INITIAL_ATR_STOP
    assert result.trades[0].exit_reference_price == Decimal("90")


def test_partial_exit_friction_and_remaining_position_reconcile() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.HOLD, open_price="110", high="121", low="95", close="115"),
        profit=ProfitManagementPolicyName.PARTIAL_2R,
        slippage_bps="5",
        commission="1",
    )
    attribution = PortfolioAttributionCalculator().calculate(result)

    assert result.trades[0].exit_reference_price == Decimal("120.0500")
    assert result.trades[0].exit_price == Decimal("119.98997500")
    assert result.trades[0].exit_commission == Decimal("1")
    assert len(result.open_positions) == 1
    assert attribution.reconciliation_residual.copy_abs() < Decimal("0.00000001")
    assert attribution.total_pnl == result.final_equity - result.initial_capital


def test_partial_exit_then_strategy_exit_reconciles_full_position_accounting() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.SELL, open_price="110", high="121", low="95", close="115"),
        bar(3, Signal.HOLD, open_price="112", high="113", low="111", close="112"),
        profit=ProfitManagementPolicyName.PARTIAL_2R,
        slippage_bps="5",
        commission="1",
    )
    attribution = PortfolioAttributionCalculator().calculate(result)

    assert [trade.exit_reason for trade in result.trades] == [
        TradeManagementExitReason.PARTIAL_PROFIT_2R,
        TradeManagementExitReason.STRATEGY_EXIT,
    ]
    assert result.open_positions == ()
    assert result.equity_curve[-1].cash == result.final_equity
    assert attribution.total_pnl == result.final_equity - result.initial_capital
    assert attribution.reconciliation_residual.copy_abs() < Decimal("0.00000001")


def test_legitimate_buy_signal_after_stop_can_reenter_without_cooldown() -> None:
    result = run(
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.BUY, open_price="95", high="96", low="89", close="91"),
        bar(3, Signal.HOLD, open_price="92", high="94", low="91", close="93"),
    )

    assert result.trades[0].exit_reason == TradeManagementExitReason.INITIAL_ATR_STOP
    assert len(result.open_positions) == 1
    assert result.open_positions[0].entry_day == START + timedelta(days=3)
    assert result.trade_management_diagnostics.reentry_count == 1
    assert result.trade_management_diagnostics.average_sessions_to_reentry == Decimal("1")


def test_signal_day_low_invalidation_uses_frozen_completed_signal_low() -> None:
    configured = ConfiguredTradeManagementPolicy(
        TradeManagementConfig(protective_stop=ProtectiveStopPolicyName.SIGNAL_DAY_LOW)
    )
    assert configured.initial_stop(
        entry_price=Decimal("100"), atr=Decimal("999"), signal_bar_low=Decimal("94")
    ) == Decimal("94")
    assert (
        configured.initial_stop(entry_price=Decimal("100"), atr=None, signal_bar_low=Decimal("101"))
        is None
    )


def test_stop_execution_accounting_and_repeated_runs_are_deterministic() -> None:
    bars = (
        bar(0, Signal.BUY),
        bar(1, Signal.HOLD, open_price="100", high="101", low="99", close="100"),
        bar(2, Signal.HOLD, open_price="95", high="96", low="89", close="91"),
    )

    first = run(*bars, slippage_bps="5", commission="1")
    second = run(*bars, slippage_bps="5", commission="1")
    attribution = PortfolioAttributionCalculator().calculate(first)

    assert first == second
    assert first.equity_curve[-1].cash == first.final_equity
    assert attribution.total_pnl == first.final_equity - first.initial_capital
    assert attribution.reconciliation_residual.copy_abs() < Decimal("0.00000001")
