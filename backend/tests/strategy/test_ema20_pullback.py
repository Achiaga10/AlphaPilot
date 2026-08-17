from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.ema20_pullback import (
    EMA20PullbackStrategy,
)
from alphapilot.strategy.signal import Signal


def create_company() -> Company:
    return Company(
        id=uuid4(),
        ticker="TEST",
        name="Test Company",
        exchange="NASDAQ",
        sector="Technology",
        industry="Software",
        is_active=True,
    )


def create_candle(
    company_id: UUID,
    trading_day: date,
    close: Decimal,
    low: Decimal | None = None,
) -> DailyCandle:
    candle_low = low if low is not None else close - Decimal("2")

    return DailyCandle(
        id=uuid4(),
        company_id=company_id,
        trading_day=trading_day,
        open=close,
        high=close + Decimal("2"),
        low=candle_low,
        close=close,
        volume=100000,
    )


def create_uptrend_candles(
    company_id: UUID,
) -> list[DailyCandle]:
    start = date(2026, 1, 1)

    candles = [
        create_candle(
            company_id=company_id,
            trading_day=start + timedelta(days=index),
            close=Decimal(100 + index),
        )
        for index in range(60)
    ]

    candles[-1].low = Decimal("149.00")

    return candles


def test_ema20_pullback_returns_buy() -> None:
    company = create_company()

    candles = create_uptrend_candles(
        company.id,
    )

    strategy = EMA20PullbackStrategy()

    signal = strategy.generate_signal(
        company,
        candles,
    )

    assert signal == Signal.BUY


def test_ema20_pullback_returns_hold_without_pullback() -> None:
    company = create_company()

    candles = create_uptrend_candles(
        company.id,
    )

    candles[-1].low = Decimal("155.00")

    strategy = EMA20PullbackStrategy()

    signal = strategy.generate_signal(
        company,
        candles,
    )

    assert signal == Signal.HOLD


def test_ema20_pullback_returns_sell_on_trend_breakdown() -> None:
    company = create_company()

    start = date(2026, 1, 1)

    candles = [
        create_candle(
            company_id=company.id,
            trading_day=start + timedelta(days=index),
            close=Decimal(200 - index),
        )
        for index in range(60)
    ]

    strategy = EMA20PullbackStrategy()

    signal = strategy.generate_signal(
        company,
        candles,
    )

    assert signal == Signal.SELL


def test_ema20_pullback_returns_hold_with_insufficient_data() -> None:
    company = create_company()

    start = date(2026, 1, 1)

    candles = [
        create_candle(
            company_id=company.id,
            trading_day=start + timedelta(days=index),
            close=Decimal(100 + index),
        )
        for index in range(20)
    ]

    strategy = EMA20PullbackStrategy()

    signal = strategy.generate_signal(
        company,
        candles,
    )

    assert signal == Signal.HOLD
