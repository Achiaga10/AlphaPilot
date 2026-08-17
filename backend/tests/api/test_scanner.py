from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.scanner.scanner import Scanner


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


@pytest.mark.asyncio
async def test_scanner_returns_buy_signal(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark_ticker = f"B{uuid4().hex[:8].upper()}"

    stock_ticker = f"T{uuid4().hex[:8].upper()}"

    monkeypatch.setattr(
        Scanner,
        "MARKET_BENCHMARK_TICKER",
        benchmark_ticker,
    )

    benchmark_company = Company(
        id=uuid4(),
        ticker=benchmark_ticker,
        name="Benchmark",
        exchange="NYSE",
        sector="ETF",
        industry="Benchmark",
        is_active=True,
    )

    stock_company = Company(
        id=uuid4(),
        ticker=stock_ticker,
        name="Test Company",
        exchange="NASDAQ",
        sector="Technology",
        industry="Software",
        is_active=True,
    )

    db_session.add_all(
        [
            benchmark_company,
            stock_company,
        ]
    )

    await db_session.commit()

    today = date.today()

    #
    # Bullish benchmark:
    # last price is above SMA200.
    #
    benchmark_start = today - timedelta(days=219)

    benchmark_candles = [
        create_candle(
            company_id=benchmark_company.id,
            trading_day=(benchmark_start + timedelta(days=index)),
            close=Decimal("300.00"),
        )
        for index in range(220)
    ]

    benchmark_candles[-1].close = Decimal("350.00")
    benchmark_candles[-1].high = Decimal("352.00")
    benchmark_candles[-1].low = Decimal("348.00")

    #
    # Stock in EMA20 pullback setup.
    #
    stock_start = today - timedelta(days=59)

    stock_candles = [
        create_candle(
            company_id=stock_company.id,
            trading_day=(stock_start + timedelta(days=index)),
            close=Decimal(100 + index),
        )
        for index in range(60)
    ]

    stock_candles[-1].low = Decimal("149.00")

    db_session.add_all(benchmark_candles + stock_candles)

    await db_session.commit()

    response = await client.get(
        "/api/v1/scanner/signals",
    )

    assert response.status_code == 200

    data = response.json()

    #
    # Scanner scans the entire database.
    # Other tests may already have created companies,
    # so we only validate the company created by this test.
    #
    matching_signals = [signal for signal in data if signal["ticker"] == stock_ticker]

    assert len(matching_signals) == 1

    signal = matching_signals[0]

    assert signal["ticker"] == stock_ticker
    assert signal["signal"] == "BUY"
    assert signal["price"] == 159.0

    #
    # Benchmark must never appear as a trading candidate.
    #
    returned_tickers = {item["ticker"] for item in data}

    assert benchmark_ticker not in returned_tickers
