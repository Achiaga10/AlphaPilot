from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class CanonicalCandleRow:
    ticker: str
    trading_day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def canonical_candle_line(row: CanonicalCandleRow) -> bytes:
    fields = (
        row.ticker.strip().upper(),
        row.trading_day.isoformat(),
        canonical_decimal(row.open),
        canonical_decimal(row.high),
        canonical_decimal(row.low),
        canonical_decimal(row.close),
        str(int(row.volume)),
    )
    return ("|".join(fields) + "\n").encode("utf-8")


def hash_candle_rows(rows: Iterable[CanonicalCandleRow]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: (item.ticker.strip().upper(), item.trading_day)):
        digest.update(canonical_candle_line(row))
    return digest.hexdigest()


def hash_universe(tickers: Iterable[str]) -> str:
    normalized = sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})
    payload = "".join(f"{ticker}\n" for ticker in normalized).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
