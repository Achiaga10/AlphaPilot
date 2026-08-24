from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from alphapilot.backtesting.engine import BacktestingEngine
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import (
    MarketRegime,
    SignalReason,
    StrategyEvaluation,
)
from alphapilot.strategy.signal import Signal


class RecordingStrategy(TradingStrategy):
    def __init__(self) -> None:
        self.calls: list[
            tuple[
                date,
                date | None,
                int,
                int,
            ]
        ] = []

    def evaluate(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> StrategyEvaluation:
        stock_day = candles[-1].trading_day

        benchmark_day = (
            context.benchmark_candles[-1].trading_day
            if context is not None and context.benchmark_candles
            else None
        )

        benchmark_count = len(context.benchmark_candles) if context is not None else 0

        self.calls.append(
            (
                stock_day,
                benchmark_day,
                len(candles),
                benchmark_count,
            )
        )

        return StrategyEvaluation(
            signal=Signal.HOLD,
            reason=SignalReason.INSUFFICIENT_DATA,
            market_regime=MarketRegime.UNKNOWN,
        )


def create_company() -> Company:
    return Company(
        id=uuid4(),
        ticker="AAPL",
        name="Apple",
        exchange="NASDAQ",
        sector="Technology",
        industry="Consumer Electronics",
        is_active=True,
    )


def create_candle(
    company_id: UUID,
    trading_day: date,
    close: str,
) -> DailyCandle:
    close_value = Decimal(close)

    return DailyCandle(
        id=uuid4(),
        company_id=company_id,
        trading_day=trading_day,
        open=close_value,
        high=close_value + Decimal("1"),
        low=close_value - Decimal("1"),
        close=close_value,
        volume=100000,
    )


def test_engine_never_exposes_future_candles() -> None:
    company = create_company()

    start_day = date(
        2026,
        1,
        5,
    )

    stock_candles = [
        create_candle(
            company.id,
            start_day + timedelta(days=index),
            str(100 + index),
        )
        for index in range(3)
    ]

    benchmark_candles = [
        create_candle(
            uuid4(),
            start_day + timedelta(days=index),
            str(500 + index),
        )
        for index in range(4)
    ]

    strategy = RecordingStrategy()

    engine = BacktestingEngine(strategy)

    result = engine.run(
        company,
        stock_candles,
        benchmark_ticker="SPY",
        benchmark_candles=benchmark_candles,
    )

    assert result.total_bars == 3

    assert len(strategy.calls) == 3

    for (
        stock_day,
        benchmark_day,
        _,
        _,
    ) in strategy.calls:
        assert benchmark_day is not None

        assert benchmark_day <= stock_day

    assert strategy.calls[0][0] == (start_day)

    assert strategy.calls[1][0] == (start_day + timedelta(days=1))

    assert strategy.calls[2][0] == (start_day + timedelta(days=2))


def test_engine_preserves_history_before_backtest_start() -> None:
    company = create_company()

    history_start = date(
        2026,
        1,
        1,
    )

    stock_candles = [
        create_candle(
            company.id,
            history_start + timedelta(days=index),
            str(100 + index),
        )
        for index in range(60)
    ]

    benchmark_candles = [
        create_candle(
            uuid4(),
            history_start + timedelta(days=index),
            str(500 + index),
        )
        for index in range(60)
    ]

    strategy = RecordingStrategy()

    engine = BacktestingEngine(strategy)

    backtest_start = history_start + timedelta(days=59)

    result = engine.run(
        company,
        stock_candles,
        benchmark_ticker="SPY",
        benchmark_candles=benchmark_candles,
        start=backtest_start,
    )

    assert result.total_bars == 1

    assert len(strategy.calls) == 1

    (
        stock_day,
        benchmark_day,
        stock_count,
        benchmark_count,
    ) = strategy.calls[0]

    assert stock_day == backtest_start
    assert benchmark_day == backtest_start

    assert stock_count == 60
    assert benchmark_count == 60
