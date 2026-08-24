from datetime import date
from decimal import Decimal

from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
)
from alphapilot.backtesting.simulator import (
    TradeSimulator,
)
from alphapilot.strategy.evaluation import (
    MarketRegime,
    SignalReason,
    StrategyEvaluation,
)
from alphapilot.strategy.signal import Signal


def create_evaluation(
    signal: Signal,
) -> StrategyEvaluation:
    if signal == Signal.BUY:
        reason = SignalReason.EMA20_PULLBACK_RECLAIM

    elif signal == Signal.SELL:
        reason = SignalReason.TREND_BREAKDOWN

    else:
        reason = SignalReason.NO_PULLBACK

    return StrategyEvaluation(
        signal=signal,
        reason=reason,
        market_regime=MarketRegime.BULLISH,
    )


def create_bar(
    trading_day: date,
    *,
    open_price: str,
    close: str,
    signal: Signal,
) -> BacktestBarResult:
    return BacktestBarResult(
        trading_day=trading_day,
        open=Decimal(open_price),
        close=Decimal(close),
        evaluation=create_evaluation(signal),
    )


def test_buy_executes_at_next_day_open() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(
            2026,
            1,
            5,
        ),
        end=date(
            2026,
            1,
            6,
        ),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="100",
                close="110",
                signal=Signal.BUY,
            ),
            create_bar(
                date(2026, 1, 6),
                open_price="120",
                close="121",
                signal=Signal.HOLD,
            ),
        ),
    )

    simulator = TradeSimulator()

    result = simulator.run(backtest)

    assert result.total_trades == 0

    assert result.open_position is not None

    assert result.open_position.entry_signal_day == date(2026, 1, 5)

    assert result.open_position.entry_day == date(2026, 1, 6)

    assert result.open_position.entry_price == Decimal("120")


def test_sell_executes_at_next_day_open() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(
            2026,
            1,
            5,
        ),
        end=date(
            2026,
            1,
            7,
        ),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="100",
                close="110",
                signal=Signal.BUY,
            ),
            create_bar(
                date(2026, 1, 6),
                open_price="105",
                close="100",
                signal=Signal.SELL,
            ),
            create_bar(
                date(2026, 1, 7),
                open_price="115",
                close="116",
                signal=Signal.HOLD,
            ),
        ),
    )

    simulator = TradeSimulator()

    result = simulator.run(backtest)

    assert result.total_trades == 1

    assert result.open_position is None

    trade = result.trades[0]

    assert trade.entry_signal_day == date(2026, 1, 5)

    assert trade.entry_day == date(2026, 1, 6)

    assert trade.entry_price == Decimal("105")

    assert trade.exit_signal_day == date(2026, 1, 6)

    assert trade.exit_day == date(2026, 1, 7)

    assert trade.exit_price == Decimal("115")

    expected_return = (Decimal("115") - Decimal("105")) / Decimal("105") * Decimal("100")

    assert trade.return_pct == expected_return


def test_last_day_signal_is_not_executed() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(
            2026,
            1,
            5,
        ),
        end=date(
            2026,
            1,
            5,
        ),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="100",
                close="110",
                signal=Signal.BUY,
            ),
        ),
    )

    simulator = TradeSimulator()

    result = simulator.run(backtest)

    assert result.total_trades == 0
    assert result.open_position is None


def test_repeated_buy_does_not_add_position() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(
            2026,
            1,
            5,
        ),
        end=date(
            2026,
            1,
            8,
        ),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="100",
                close="101",
                signal=Signal.BUY,
            ),
            create_bar(
                date(2026, 1, 6),
                open_price="102",
                close="103",
                signal=Signal.BUY,
            ),
            create_bar(
                date(2026, 1, 7),
                open_price="104",
                close="100",
                signal=Signal.SELL,
            ),
            create_bar(
                date(2026, 1, 8),
                open_price="99",
                close="98",
                signal=Signal.HOLD,
            ),
        ),
    )

    simulator = TradeSimulator()

    result = simulator.run(backtest)

    assert result.total_trades == 1

    trade = result.trades[0]

    assert trade.entry_day == date(2026, 1, 6)

    assert trade.entry_price == Decimal("102")

    assert trade.exit_day == date(2026, 1, 8)

    assert trade.exit_price == Decimal("99")
