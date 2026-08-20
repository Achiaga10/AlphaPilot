from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from alphapilot.market.dto import MarketCandle
from alphapilot.market.providers.alpaca import AlpacaProvider
from alphapilot.market.providers.polygon import PolygonProvider

TICKERS = [
    "AAPL",
    "NVDA",
    "AMZN",
    "BRK.B",
    "TSLA",
]

START_DATE = date(2026, 8, 10)
END_DATE = date(2026, 8, 18)


def percent_difference(
    first: Decimal,
    second: Decimal,
) -> Decimal:
    if first == 0:
        return Decimal("0")

    return abs((second - first) / first) * Decimal("100")


def build_by_date(
    candles: list[MarketCandle],
) -> dict[date, MarketCandle]:
    return {candle.date: candle for candle in candles}


async def compare_ticker(
    ticker: str,
    polygon: PolygonProvider,
    alpaca: AlpacaProvider,
) -> None:
    polygon_candles = await polygon.get_history(
        ticker=ticker,
        start=START_DATE,
        end=END_DATE,
    )

    alpaca_candles = await alpaca.get_history(
        ticker=ticker,
        start=START_DATE,
        end=END_DATE,
    )

    polygon_by_date = build_by_date(polygon_candles)

    alpaca_by_date = build_by_date(alpaca_candles)

    shared_dates = sorted(set(polygon_by_date) & set(alpaca_by_date))

    print()
    print("=" * 70)
    print(ticker)
    print("=" * 70)

    print(f"Polygon candles: {len(polygon_candles)}")
    print(f"Alpaca candles:  {len(alpaca_candles)}")
    print(f"Shared dates:     {len(shared_dates)}")

    if not shared_dates:
        print("No shared trading days.")
        return

    max_close_difference = Decimal("0")

    for trading_day in shared_dates:
        polygon_candle = polygon_by_date[trading_day]

        alpaca_candle = alpaca_by_date[trading_day]

        close_difference = percent_difference(
            polygon_candle.close,
            alpaca_candle.close,
        )

        max_close_difference = max(
            max_close_difference,
            close_difference,
        )

        print()
        print(trading_day)

        print(
            "  Close  "
            f"Polygon={polygon_candle.close} "
            f"Alpaca={alpaca_candle.close} "
            f"Diff={close_difference:.4f}%"
        )

        print(f"  Open   Polygon={polygon_candle.open} Alpaca={alpaca_candle.open}")

        print(f"  High   Polygon={polygon_candle.high} Alpaca={alpaca_candle.high}")

        print(f"  Low    Polygon={polygon_candle.low} Alpaca={alpaca_candle.low}")

        print(f"  Volume Polygon={polygon_candle.volume} Alpaca={alpaca_candle.volume}")

    print()
    print(f"Maximum close difference: {max_close_difference:.4f}%")


async def main() -> None:
    polygon = PolygonProvider()
    alpaca = AlpacaProvider()

    for ticker in TICKERS:
        try:
            await compare_ticker(
                ticker=ticker,
                polygon=polygon,
                alpaca=alpaca,
            )

        except Exception as exc:
            print()
            print("=" * 70)
            print(f"{ticker} FAILED: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
