from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.evaluation import SignalReason
from alphapilot.strategy.micho150 import Micho150Strategy
from alphapilot.strategy.micho_entry_mode import (
    MichoEntryMode,
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
    *,
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> DailyCandle:
    return DailyCandle(
        id=uuid4(),
        company_id=company_id,
        trading_day=trading_day,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=100000,
    )


def create_flat_history(
    company_id: UUID,
    *,
    count: int,
    price: str = "100",
) -> list[DailyCandle]:
    start = date(2025, 1, 1)

    return [
        create_candle(
            company_id,
            start + timedelta(days=index),
            open_price=price,
            high=price,
            low=price,
            close=price,
        )
        for index in range(count)
    ]


def test_insufficient_data_returns_hold() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=100,
    )

    strategy = Micho150Strategy()

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.HOLD

    assert result.reason == SignalReason.INSUFFICIENT_DATA


def test_breakout_above_sma150_returns_buy() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    previous_day = candles[-1].trading_day

    candles.append(
        create_candle(
            company.id,
            previous_day + timedelta(days=1),
            open_price="100",
            high="104",
            low="99",
            close="103",
        )
    )

    strategy = Micho150Strategy()

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.BUY

    assert result.reason == SignalReason.MICHO_150_BREAKOUT

    assert result.sma150 is not None


def test_bounce_from_sma150_returns_buy() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    candles[-1] = create_candle(
        company.id,
        candles[-1].trading_day,
        open_price="101",
        high="102",
        low="100",
        close="101",
    )

    candles.append(
        create_candle(
            company.id,
            candles[-1].trading_day + timedelta(days=1),
            open_price="101",
            high="104",
            low="100",
            close="103",
        )
    )

    strategy = Micho150Strategy()

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.BUY

    assert result.reason == SignalReason.MICHO_150_BOUNCE


def test_close_below_sma150_returns_sell() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    candles.append(
        create_candle(
            company.id,
            candles[-1].trading_day + timedelta(days=1),
            open_price="100",
            high="100",
            low="95",
            close="95",
        )
    )

    strategy = Micho150Strategy()

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.SELL

    assert result.reason == SignalReason.MICHO_150_BREAKDOWN


def test_declining_sma150_blocks_entry() -> None:
    company = create_company()

    start = date(2025, 1, 1)

    candles = [
        create_candle(
            company.id,
            start + timedelta(days=index),
            open_price=str(200 - index),
            high=str(201 - index),
            low=str(199 - index),
            close=str(200 - index),
        )
        for index in range(156)
    ]

    strategy = Micho150Strategy()

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal != Signal.BUY


def test_breakout_only_allows_breakout() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    candles.append(
        create_candle(
            company.id,
            candles[-1].trading_day + timedelta(days=1),
            open_price="100",
            high="104",
            low="99",
            close="103",
        )
    )

    strategy = Micho150Strategy(
        entry_mode=(MichoEntryMode.BREAKOUT_ONLY),
    )

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.BUY

    assert result.reason == SignalReason.MICHO_150_BREAKOUT


def test_bounce_only_blocks_breakout() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    candles.append(
        create_candle(
            company.id,
            candles[-1].trading_day + timedelta(days=1),
            open_price="100",
            high="104",
            low="99",
            close="103",
        )
    )

    strategy = Micho150Strategy(
        entry_mode=(MichoEntryMode.BOUNCE_ONLY),
    )

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.HOLD

    assert result.reason == SignalReason.MICHO_150_NO_ENTRY


def test_bounce_only_allows_bounce() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    candles[-1] = create_candle(
        company.id,
        candles[-1].trading_day,
        open_price="101",
        high="102",
        low="100",
        close="101",
    )

    candles.append(
        create_candle(
            company.id,
            candles[-1].trading_day + timedelta(days=1),
            open_price="101",
            high="104",
            low="100",
            close="103",
        )
    )

    strategy = Micho150Strategy(
        entry_mode=(MichoEntryMode.BOUNCE_ONLY),
    )

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.BUY

    assert result.reason == SignalReason.MICHO_150_BOUNCE


def test_breakout_only_blocks_bounce() -> None:
    company = create_company()

    candles = create_flat_history(
        company.id,
        count=155,
        price="100",
    )

    candles[-1] = create_candle(
        company.id,
        candles[-1].trading_day,
        open_price="101",
        high="102",
        low="100",
        close="101",
    )

    candles.append(
        create_candle(
            company.id,
            candles[-1].trading_day + timedelta(days=1),
            open_price="101",
            high="104",
            low="100",
            close="103",
        )
    )

    strategy = Micho150Strategy(
        entry_mode=(MichoEntryMode.BREAKOUT_ONLY),
    )

    result = strategy.evaluate(
        company,
        candles,
    )

    assert result.signal == Signal.HOLD

    assert result.reason == SignalReason.MICHO_150_NO_ENTRY


def test_default_micho_entry_mode_is_both() -> None:
    strategy = Micho150Strategy()

    assert strategy.entry_mode == MichoEntryMode.BOTH
