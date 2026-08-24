from datetime import date
from decimal import Decimal
from uuid import uuid4

from alphapilot.backtesting.benchmark import (
    BuyAndHoldSimulator,
)
from alphapilot.backtesting.models import (
    PortfolioConfig,
)
from alphapilot.database.models.daily_candle import (
    DailyCandle,
)


def create_candle(
    trading_day: date,
    *,
    open_price: str,
    close: str,
) -> DailyCandle:
    open_value = Decimal(open_price)

    close_value = Decimal(close)

    return DailyCandle(
        id=uuid4(),
        company_id=uuid4(),
        trading_day=trading_day,
        open=open_value,
        high=max(
            open_value,
            close_value,
        ),
        low=min(
            open_value,
            close_value,
        ),
        close=close_value,
        volume=100000,
    )


def test_buy_and_hold_buys_first_open_and_holds() -> None:
    candles = [
        create_candle(
            date(2026, 1, 5),
            open_price="100",
            close="105",
        ),
        create_candle(
            date(2026, 1, 6),
            open_price="106",
            close="110",
        ),
        create_candle(
            date(2026, 1, 7),
            open_price="111",
            close="120",
        ),
    ]

    simulator = BuyAndHoldSimulator()

    result = simulator.run(
        ticker="AAPL",
        candles=candles,
        start=date(2026, 1, 5),
        end=date(2026, 1, 7),
        config=PortfolioConfig(
            initial_capital=Decimal("1000"),
        ),
    )

    assert result.open_position is not None

    assert result.open_position.shares == 10

    assert result.open_position.entry_price == Decimal("100")

    assert result.final_equity == Decimal("1200")

    assert result.total_return_pct == Decimal("20")

    assert len(result.equity_curve) == 3


def test_buy_and_hold_respects_requested_range() -> None:
    candles = [
        create_candle(
            date(2026, 1, 1),
            open_price="50",
            close="60",
        ),
        create_candle(
            date(2026, 1, 5),
            open_price="100",
            close="105",
        ),
        create_candle(
            date(2026, 1, 6),
            open_price="106",
            close="110",
        ),
    ]

    simulator = BuyAndHoldSimulator()

    result = simulator.run(
        ticker="AAPL",
        candles=candles,
        start=date(2026, 1, 5),
        end=date(2026, 1, 6),
        config=PortfolioConfig(
            initial_capital=Decimal("1000"),
        ),
    )

    assert result.open_position is not None

    assert result.open_position.entry_day == date(2026, 1, 5)

    assert result.open_position.entry_price == Decimal("100")

    assert len(result.equity_curve) == 2
