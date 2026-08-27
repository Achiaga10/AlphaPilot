from datetime import date
from decimal import Decimal

from alphapilot.research_data.hashing import (
    CanonicalCandleRow,
    canonical_candle_line,
    canonical_decimal,
    hash_candle_rows,
    hash_universe,
)


def row(ticker: str, close: str = "101.25", volume: int = 1000) -> CanonicalCandleRow:
    return CanonicalCandleRow(
        ticker=ticker,
        trading_day=date(2025, 1, 2),
        open=Decimal("100.0000"),
        high=Decimal("102.5000"),
        low=Decimal("99.2500"),
        close=Decimal(close),
        volume=volume,
    )


def test_canonical_decimal_never_uses_float_or_exponent() -> None:
    assert canonical_decimal(Decimal("100.0000")) == "100"
    assert canonical_decimal(Decimal("0.0100")) == "0.01"
    assert canonical_decimal(Decimal("-0.0000")) == "0"


def test_canonical_candle_serialization_is_explicit() -> None:
    assert canonical_candle_line(row("aapl")) == (b"AAPL|2025-01-02|100|102.5|99.25|101.25|1000\n")


def test_dataset_hash_is_order_independent_but_value_sensitive() -> None:
    first = row("AAPL")
    second = row("MSFT", "202")
    assert hash_candle_rows([first, second]) == hash_candle_rows([second, first])
    assert hash_candle_rows([first, second]) != hash_candle_rows([row("AAPL", "101.26"), second])
    assert hash_candle_rows([first, second]) != hash_candle_rows([row("AAPL", volume=1001), second])


def test_universe_hash_is_normalized_order_independent_and_member_sensitive() -> None:
    assert hash_universe(["msft", " AAPL "]) == hash_universe(["AAPL", "MSFT"])
    assert hash_universe(["AAPL", "MSFT"]) != hash_universe(["AAPL", "NVDA"])
