from datetime import date
from decimal import Decimal
from uuid import uuid4

from alphapilot.backtesting.diagnostics import (
    BacktestDiagnosticsCalculator,
)
from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
    PortfolioSimulationResult,
    PortfolioTrade,
)
from alphapilot.database.models.daily_candle import (
    DailyCandle,
)
from alphapilot.strategy.evaluation import (
    MarketRegime,
    SignalReason,
    StrategyEvaluation,
)
from alphapilot.strategy.signal import Signal


def create_evaluation(
    signal: Signal,
    reason: SignalReason,
) -> StrategyEvaluation:
    return StrategyEvaluation(
        signal=signal,
        reason=reason,
        market_regime=MarketRegime.BULLISH,
    )


def create_candle(
    trading_day: date,
    *,
    high: str,
    low: str,
) -> DailyCandle:
    high_value = Decimal(high)
    low_value = Decimal(low)

    return DailyCandle(
        id=uuid4(),
        company_id=uuid4(),
        trading_day=trading_day,
        open=low_value,
        high=high_value,
        low=low_value,
        close=high_value,
        volume=100000,
    )


def test_calculates_trade_excursions_and_giveback() -> None:
    entry_evaluation = create_evaluation(
        Signal.BUY,
        SignalReason.EMA20_PULLBACK_RECLAIM,
    )

    exit_evaluation = create_evaluation(
        Signal.SELL,
        SignalReason.TREND_BREAKDOWN,
    )

    backtest = BacktestResult(
        ticker="AAPL",
        start=date(2026, 1, 5),
        end=date(2026, 1, 9),
        bars=(
            BacktestBarResult(
                trading_day=date(2026, 1, 5),
                open=Decimal("95"),
                close=Decimal("100"),
                evaluation=entry_evaluation,
            ),
            BacktestBarResult(
                trading_day=date(2026, 1, 8),
                open=Decimal("120"),
                close=Decimal("115"),
                evaluation=exit_evaluation,
            ),
            BacktestBarResult(
                trading_day=date(2026, 1, 9),
                open=Decimal("115"),
                close=Decimal("114"),
                evaluation=exit_evaluation,
            ),
        ),
    )

    trade = PortfolioTrade(
        entry_signal_day=date(2026, 1, 5),
        entry_day=date(2026, 1, 6),
        entry_price=Decimal("100"),
        exit_signal_day=date(2026, 1, 8),
        exit_day=date(2026, 1, 9),
        exit_price=Decimal("115"),
        shares=10,
        entry_commission=Decimal("0"),
        exit_commission=Decimal("0"),
    )

    portfolio = PortfolioSimulationResult(
        ticker="AAPL",
        initial_capital=Decimal("1000"),
        final_equity=Decimal("1150"),
        equity_curve=(),
        trades=(trade,),
        open_position=None,
    )

    candles = [
        create_candle(
            date(2026, 1, 6),
            high="120",
            low="95",
        ),
        create_candle(
            date(2026, 1, 7),
            high="140",
            low="105",
        ),
        create_candle(
            date(2026, 1, 8),
            high="130",
            low="110",
        ),
    ]

    calculator = BacktestDiagnosticsCalculator()

    result = calculator.calculate(
        backtest,
        portfolio,
        candles,
    )

    assert len(result.trades) == 1

    diagnostic = result.trades[0]

    assert diagnostic.return_pct == Decimal("15")

    assert diagnostic.mfe_pct == Decimal("40")

    assert diagnostic.mae_pct == Decimal("-5")

    expected_giveback = (Decimal("140") - Decimal("115")) / Decimal("140") * Decimal("100")

    assert diagnostic.peak_giveback_pct == expected_giveback

    assert diagnostic.entry_reason == SignalReason.EMA20_PULLBACK_RECLAIM

    assert diagnostic.exit_reason == SignalReason.TREND_BREAKDOWN
