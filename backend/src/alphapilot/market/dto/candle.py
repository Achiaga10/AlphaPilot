from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class MarketCandle:
    """Represents one daily market candle returned by a provider."""

    date: date

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    volume: int
