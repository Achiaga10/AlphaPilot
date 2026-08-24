from datetime import date
from decimal import Decimal

from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
    PortfolioConfig,
)
from alphapilot.backtesting.portfolio import (
    PortfolioSimulator,
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


def test_portfolio_executes_buy_at_next_open() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(2026, 1, 5),
        end=date(2026, 1, 6),
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
                close="125",
                signal=Signal.HOLD,
            ),
        ),
    )

    simulator = PortfolioSimulator(PortfolioConfig(initial_capital=Decimal("1000")))

    result = simulator.run(backtest)

    assert result.open_position is not None

    assert result.open_position.shares == 8

    assert result.open_position.entry_price == Decimal("120")

    assert len(result.equity_curve) == 2

    first_day = result.equity_curve[0]

    assert first_day.equity == Decimal("1000")

    second_day = result.equity_curve[1]

    assert second_day.cash == Decimal("40")

    assert second_day.shares == 8

    assert second_day.equity == Decimal("1040")

    assert result.final_equity == Decimal("1040")

    assert result.total_return_pct == Decimal("4")


def test_portfolio_executes_sell_at_next_open() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(2026, 1, 5),
        end=date(2026, 1, 7),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="90",
                close="95",
                signal=Signal.BUY,
            ),
            create_bar(
                date(2026, 1, 6),
                open_price="100",
                close="105",
                signal=Signal.SELL,
            ),
            create_bar(
                date(2026, 1, 7),
                open_price="110",
                close="108",
                signal=Signal.HOLD,
            ),
        ),
    )

    simulator = PortfolioSimulator(PortfolioConfig(initial_capital=Decimal("1000")))

    result = simulator.run(backtest)

    assert result.open_position is None

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.shares == 10

    assert trade.entry_price == Decimal("100")

    assert trade.exit_price == Decimal("110")

    assert trade.pnl == Decimal("100")

    assert trade.return_pct == Decimal("10")

    assert result.final_equity == Decimal("1100")

    assert result.total_return_pct == Decimal("10")


def test_portfolio_applies_commission_and_slippage() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(2026, 1, 5),
        end=date(2026, 1, 7),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="90",
                close="95",
                signal=Signal.BUY,
            ),
            create_bar(
                date(2026, 1, 6),
                open_price="100",
                close="100",
                signal=Signal.SELL,
            ),
            create_bar(
                date(2026, 1, 7),
                open_price="110",
                close="110",
                signal=Signal.HOLD,
            ),
        ),
    )

    config = PortfolioConfig(
        initial_capital=Decimal("1000"),
        commission_per_order=Decimal("5"),
        slippage_bps=Decimal("100"),
    )

    simulator = PortfolioSimulator(config)

    result = simulator.run(backtest)

    assert len(result.trades) == 1

    trade = result.trades[0]

    assert trade.shares == 9

    assert trade.entry_price == Decimal("101")

    assert trade.exit_price == Decimal("108.90")

    assert trade.pnl == Decimal("61.10")

    assert result.final_equity == Decimal("1061.10")


def test_last_day_signal_is_not_executed_by_portfolio() -> None:
    backtest = BacktestResult(
        ticker="AAPL",
        start=date(2026, 1, 5),
        end=date(2026, 1, 5),
        bars=(
            create_bar(
                date(2026, 1, 5),
                open_price="100",
                close="110",
                signal=Signal.BUY,
            ),
        ),
    )

    simulator = PortfolioSimulator(PortfolioConfig(initial_capital=Decimal("1000")))

    result = simulator.run(backtest)

    assert result.open_position is None

    assert result.trades == ()

    assert result.final_equity == Decimal("1000")
