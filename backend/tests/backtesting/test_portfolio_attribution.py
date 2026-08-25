from datetime import date, timedelta
from decimal import Decimal

from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal

START = date(2025, 1, 1)


def bar(day: int, signal: Signal, price: str) -> BacktestBarResult:
    return BacktestBarResult(
        trading_day=START + timedelta(days=day),
        open=Decimal(price),
        close=Decimal(price),
        evaluation=StrategyEvaluation(signal=signal, reason=SignalReason.NO_PULLBACK),
    )


def result(ticker: str, *bars: BacktestBarResult) -> BacktestResult:
    return BacktestResult(
        ticker=ticker, start=bars[0].trading_day, end=bars[-1].trading_day, bars=bars
    )


def test_realized_unrealized_friction_and_final_equity_reconcile() -> None:
    portfolio = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("2000"),
            max_positions=2,
            slippage_bps=Decimal("5"),
        )
    ).run(
        {
            "AAA": result(
                "AAA",
                bar(0, Signal.BUY, "100"),
                bar(1, Signal.SELL, "100"),
                bar(2, Signal.HOLD, "110"),
            ),
            "BBB": result(
                "BBB",
                bar(0, Signal.BUY, "100"),
                bar(1, Signal.HOLD, "100"),
                bar(2, Signal.HOLD, "120"),
            ),
        },
        ticker_sectors={"AAA": "Technology", "BBB": None},
    )
    attribution = PortfolioAttributionCalculator().calculate(portfolio)
    by_ticker = {row.ticker: row for row in attribution.tickers}

    assert portfolio.trades[0].entry_price == Decimal("100.0500")
    assert portfolio.trades[0].exit_price == Decimal("109.9450")
    assert by_ticker["AAA"].realized_pnl == portfolio.trades[0].pnl
    assert by_ticker["BBB"].unrealized_pnl == portfolio.open_positions[0].unrealized_pnl(
        dict(portfolio.final_prices)["BBB"]
    )
    assert attribution.transaction_friction > 0
    assert attribution.total_pnl == portfolio.final_equity - portfolio.initial_capital
    assert attribution.reconciliation_residual == 0
    assert {row.sector for row in attribution.sectors} == {"Technology", "Unknown"}


def test_top_contributors_negative_values_and_hhi_are_correct() -> None:
    portfolio = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("3000"), max_positions=3)
    ).run(
        {
            "AAA": result(
                "AAA",
                bar(0, Signal.BUY, "100"),
                bar(1, Signal.HOLD, "100"),
                bar(2, Signal.HOLD, "130"),
            ),
            "BBB": result(
                "BBB",
                bar(0, Signal.BUY, "100"),
                bar(1, Signal.HOLD, "100"),
                bar(2, Signal.HOLD, "120"),
            ),
            "CCC": result(
                "CCC",
                bar(0, Signal.BUY, "100"),
                bar(1, Signal.HOLD, "100"),
                bar(2, Signal.HOLD, "90"),
            ),
        }
    )
    attribution = PortfolioAttributionCalculator().calculate(portfolio)

    assert [row.ticker for row in attribution.tickers] == ["AAA", "BBB", "CCC"]
    assert attribution.top_1_pnl == Decimal("300")
    assert attribution.top_5_pnl == attribution.total_pnl
    assert attribution.top_10_pnl == attribution.total_pnl
    assert attribution.positive_tickers == 2
    assert attribution.negative_tickers == 1
    assert attribution.top_1_positive_pnl_share_pct == Decimal("60")
    assert attribution.top_5_positive_pnl_share_pct == Decimal("100")
    assert attribution.positive_pnl_hhi == Decimal("0.52")


def test_zero_cost_is_unchanged_and_more_slippage_cannot_improve_cash_flow() -> None:
    inputs = {
        "AAA": result(
            "AAA", bar(0, Signal.BUY, "100"), bar(1, Signal.SELL, "100"), bar(2, Signal.HOLD, "110")
        )
    }
    zero = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1)
    ).run(inputs)
    low = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("1000"), max_positions=1, slippage_bps=Decimal("5")
        )
    ).run(inputs)
    conservative = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("1000"), max_positions=1, slippage_bps=Decimal("15")
        )
    ).run(inputs)

    assert zero.trades[0].entry_price == Decimal("100")
    assert zero.trades[0].exit_price == Decimal("110")
    assert zero.final_equity > low.final_equity > conservative.final_equity
