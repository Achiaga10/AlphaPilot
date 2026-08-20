from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
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


async def seed_market_and_stock(
    db_session: AsyncSession,
    benchmark_ticker: str,
    stock_ticker: str,
    *,
    pullback: bool,
) -> None:
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

    stock_start = today - timedelta(days=59)

    stock_candles = [
        create_candle(
            company_id=stock_company.id,
            trading_day=(stock_start + timedelta(days=index)),
            close=Decimal(100 + index),
        )
        for index in range(60)
    ]

    if pullback:
        stock_candles[-1].low = Decimal("149.00")
    else:
        stock_candles[-1].low = Decimal("155.00")

    db_session.add_all(benchmark_candles + stock_candles)

    await db_session.commit()


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

    await seed_market_and_stock(
        db_session,
        benchmark_ticker,
        stock_ticker,
        pullback=True,
    )

    universe_repository = IndexConstituentRepository(
        db_session,
    )

    await universe_repository.sync_current(
        "^GSPC",
        [
            stock_ticker,
        ],
    )

    response = await client.get(
        "/api/v1/scanner/signals",
    )

    assert response.status_code == 200

    data = response.json()

    matching_signals = [signal for signal in data if signal["ticker"] == stock_ticker]

    assert len(matching_signals) == 1

    signal = matching_signals[0]

    assert signal["ticker"] == stock_ticker
    assert signal["signal"] == "BUY"
    assert signal["price"] == 159.0

    assert signal["ema20"] == pytest.approx(149.5)

    assert signal["ema50"] == pytest.approx(134.5)

    assert signal["market_regime"] == "BULLISH"

    assert signal["reason"] == "EMA20_PULLBACK_RECLAIM"

    returned_tickers = {item["ticker"] for item in data}

    assert benchmark_ticker not in returned_tickers


@pytest.mark.asyncio
async def test_scanner_evaluate_returns_hold_reason(
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

    await seed_market_and_stock(
        db_session,
        benchmark_ticker,
        stock_ticker,
        pullback=False,
    )

    # Intentionally do NOT add stock_ticker
    # to the S&P 500 universe.
    #
    # evaluate/{ticker} must work for any
    # company that exists in AlphaPilot.

    response = await client.get(
        f"/api/v1/scanner/evaluate/{stock_ticker}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["ticker"] == stock_ticker
    assert data["signal"] == "HOLD"
    assert data["price"] == 159.0

    assert data["ema20"] == pytest.approx(149.5)

    assert data["ema50"] == pytest.approx(134.5)

    assert data["market_regime"] == "BULLISH"

    assert data["reason"] == "NO_PULLBACK"


@pytest.mark.asyncio
async def test_scanner_evaluate_company_not_found(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/scanner/evaluate/DOESNOTEXIST",
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": ("Company DOESNOTEXIST not found"),
    }
