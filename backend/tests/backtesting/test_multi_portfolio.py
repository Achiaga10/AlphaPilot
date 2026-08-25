from datetime import date, timedelta
from decimal import Decimal

import pytest

from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
)
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal

START = date(2026, 1, 5)


def bar(
    offset: int,
    *,
    signal: Signal,
    open_price: str = "100",
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
        close=Decimal(close),
        evaluation=StrategyEvaluation(signal=signal, reason=reason),
    )


def backtest(ticker: str, *bars: BacktestBarResult) -> BacktestResult:
    return BacktestResult(
        ticker=ticker,
        start=bars[0].trading_day if bars else None,
        end=bars[-1].trading_day if bars else None,
        bars=bars,
    )


def test_two_stocks_share_cash_and_can_be_held_simultaneously() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=2)
    ).run(
        {
            "AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
            "BBB": backtest("BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        }
    )

    assert len(result.open_positions) == 2
    assert {position.ticker for position in result.open_positions} == {"AAA", "BBB"}
    assert [position.shares for position in result.open_positions] == [5, 5]
    assert result.equity_curve[-1].cash == Decimal("0")
    assert result.equity_curve[-1].cash >= 0
    assert result.equity_curve[-1].equity == Decimal("1000")


def test_max_positions_and_deterministic_ticker_priority_are_enforced() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1)
    ).run(
        {
            "BBB": backtest("BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
            "AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        }
    )

    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticker == "AAA"
    assert result.open_positions[0].shares == 10


def test_whole_share_position_sizing_and_cash_floor() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=3)
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.HOLD, open_price="120"),
            )
        }
    )

    assert result.open_positions[0].shares == 2
    assert result.equity_curve[-1].cash == Decimal("760")
    assert min(point.cash for point in result.equity_curve) >= 0


def test_commission_and_slippage_apply_to_entry_and_exit() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("1000"),
            max_positions=1,
            commission_per_order=Decimal("5"),
            slippage_bps=Decimal("100"),
        )
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL, open_price="100", close="100"),
                bar(2, signal=Signal.HOLD, open_price="110", close="110"),
            )
        }
    )

    trade = result.trades[0]
    assert trade.entry_price == Decimal("101.00")
    assert trade.exit_price == Decimal("108.90")
    assert trade.shares == 9
    assert trade.entry_commission == Decimal("5")
    assert trade.exit_commission == Decimal("5")


def test_entry_and_exit_use_next_available_open() -> None:
    result = MultiPortfolioSimulator().run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY, close="130"),
                bar(3, signal=Signal.SELL, open_price="120", close="90"),
                bar(7, signal=Signal.HOLD, open_price="80", close="85"),
            )
        }
    )

    trade = result.trades[0]
    assert trade.entry_signal_day == START
    assert trade.entry_day == START + timedelta(days=3)
    assert trade.entry_price == Decimal("120")
    assert trade.exit_signal_day == START + timedelta(days=3)
    assert trade.exit_day == START + timedelta(days=7)
    assert trade.exit_price == Decimal("80")


def test_exit_releases_cash_before_same_day_entry() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1)
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL),
                bar(2, signal=Signal.HOLD),
            ),
            "BBB": backtest(
                "BBB",
                bar(1, signal=Signal.BUY),
                bar(2, signal=Signal.HOLD),
            ),
        }
    )

    assert len(result.trades) == 1
    assert result.trades[0].ticker == "AAA"
    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticker == "BBB"
    assert result.open_positions[0].entry_day == START + timedelta(days=2)


def test_repeated_buy_and_flat_sell_are_ignored() -> None:
    result = MultiPortfolioSimulator().run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.BUY),
                bar(2, signal=Signal.HOLD),
            ),
            "BBB": backtest(
                "BBB",
                bar(0, signal=Signal.SELL),
                bar(1, signal=Signal.HOLD),
            ),
        }
    )

    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticker == "AAA"
    assert result.open_positions[0].entry_signal_day == START
    assert result.trades == ()


def test_last_day_buy_and_sell_cannot_execute() -> None:
    no_entry = MultiPortfolioSimulator().run({"AAA": backtest("AAA", bar(0, signal=Signal.BUY))})
    open_at_end = MultiPortfolioSimulator(MultiPortfolioConfig(max_positions=1)).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL, close="125"),
            )
        }
    )

    assert no_entry.open_positions == ()
    assert no_entry.trades == ()
    assert len(open_at_end.open_positions) == 1
    assert open_at_end.trades == ()
    assert open_at_end.final_equity == Decimal("125000")


def test_daily_equity_includes_all_positions_and_marks_final_close() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=2)
    ).run(
        {
            "AAA": backtest(
                "AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD, close="110")
            ),
            "BBB": backtest(
                "BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD, close="120")
            ),
        }
    )

    final = result.equity_curve[-1]
    assert final.open_positions == 2
    assert final.invested_value == Decimal("1150")
    assert final.equity == Decimal("1150")
    assert result.final_equity == Decimal("1150")


def test_config_rejects_invalid_constraints() -> None:
    with pytest.raises(ValueError, match="max_positions"):
        MultiPortfolioConfig(max_positions=0)

    with pytest.raises(ValueError, match="initial_capital"):
        MultiPortfolioConfig(initial_capital=Decimal("0"))
