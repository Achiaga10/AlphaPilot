from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.portfolio.risk import AverageTrueRangeCalculator

START = date(2025, 1, 1)


def candle(day: int, high: str, low: str, close: str) -> DailyCandle:
    return DailyCandle(
        id=uuid4(),
        company_id=uuid4(),
        trading_day=START + timedelta(days=day),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1000,
    )


def test_true_range_uses_largest_gap_or_intraday_range() -> None:
    calculator = AverageTrueRangeCalculator()
    assert calculator.true_range(candle(1, "115", "105", "110"), Decimal("100")) == 15
    assert calculator.true_range(candle(1, "105", "90", "100"), Decimal("100")) == 15


def test_atr14_formula_no_lookahead_and_insufficient_history() -> None:
    candles = [candle(0, "101", "99", "100")]
    candles.extend(candle(day, "102", "100", "101") for day in range(1, 15))
    calculator = AverageTrueRangeCalculator()
    signal_day = START + timedelta(days=14)
    expected = calculator.calculate(candles, signal_day=signal_day)
    with_future = calculator.calculate(
        [*candles, candle(15, "1000", "1", "500")], signal_day=signal_day
    )
    assert expected == Decimal("2")
    assert with_future == expected
    assert calculator.calculate(candles[:14], signal_day=signal_day) is None


def test_zero_atr_is_invalid() -> None:
    flat = [candle(day, "100", "100", "100") for day in range(15)]
    assert (
        AverageTrueRangeCalculator().calculate(flat, signal_day=START + timedelta(days=14)) is None
    )
