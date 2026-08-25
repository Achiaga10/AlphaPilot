from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from alphapilot.backtesting.ranking_features import RelativeStrength20Calculator
from alphapilot.database.models.daily_candle import DailyCandle

START = date(2025, 1, 1)


def candles(closes: list[str], *, start: date = START) -> list[DailyCandle]:
    return [
        DailyCandle(
            id=uuid4(),
            company_id=uuid4(),
            trading_day=start + timedelta(days=index),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]


def test_rs20_formula_is_stock_return_minus_spy_return() -> None:
    stock = candles(["100", *(["100"] * 19), "120"])
    spy = candles(["200", *(["200"] * 19), "220"])

    score = RelativeStrength20Calculator().calculate(
        stock_candles=stock,
        benchmark_candles=spy,
        signal_day=START + timedelta(days=20),
    )

    assert score == Decimal("0.10")


def test_negative_relative_strength_is_preserved() -> None:
    stock = candles(["100", *(["100"] * 19), "90"])
    spy = candles(["100", *(["100"] * 19), "110"])

    score = RelativeStrength20Calculator().calculate(
        stock_candles=stock,
        benchmark_candles=spy,
        signal_day=START + timedelta(days=20),
    )

    assert score == Decimal("-0.20")


def test_future_stock_and_spy_data_cannot_change_signal_day_score() -> None:
    signal_day = START + timedelta(days=20)
    base_stock = candles(["100", *(["100"] * 19), "120"])
    base_spy = candles(["100", *(["100"] * 19), "110"])
    calculator = RelativeStrength20Calculator()
    expected = calculator.calculate(
        stock_candles=base_stock,
        benchmark_candles=base_spy,
        signal_day=signal_day,
    )

    with_future = calculator.calculate(
        stock_candles=[*base_stock, *candles(["999", "1"], start=signal_day + timedelta(days=1))],
        benchmark_candles=[*base_spy, *candles(["1", "999"], start=signal_day + timedelta(days=1))],
        signal_day=signal_day,
    )

    assert expected == Decimal("0.10")
    assert with_future == expected


def test_missing_history_returns_none_without_fabricating_score() -> None:
    calculator = RelativeStrength20Calculator()

    assert (
        calculator.calculate(
            stock_candles=candles(["100"] * 20),
            benchmark_candles=candles(["100"] * 21),
            signal_day=START + timedelta(days=20),
        )
        is None
    )
    assert (
        calculator.calculate(
            stock_candles=candles(["100"] * 21),
            benchmark_candles=candles(["100"] * 20),
            signal_day=START + timedelta(days=20),
        )
        is None
    )
