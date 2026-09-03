from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from alphapilot.strategy.ema20_pullback import EMA20_PULLBACK_UPPER_BOUND


class Ema20EntryPriceSource(StrEnum):
    COMPLETED_SESSION_CLOSE = "COMPLETED_SESSION_CLOSE"
    ALPACA_LIVE_SNAPSHOT = "ALPACA_LIVE_SNAPSHOT"


class Ema20AnchorSource(StrEnum):
    COMPLETED_SIGNAL_SESSION_EMA20 = "COMPLETED_SIGNAL_SESSION_EMA20"


class Ema20EntryRelation(StrEnum):
    BELOW = "BELOW"
    TOUCHING_OR_NEAR = "TOUCHING_OR_NEAR"
    EXTENDED_ABOVE = "EXTENDED_ABOVE"
    UNAVAILABLE = "UNAVAILABLE"


class Ema20EntrySafetyStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class Ema20EntrySafetyReason(StrEnum):
    ENTRY_BELOW_EMA20 = "ENTRY_BELOW_EMA20"
    ENTRY_TOUCHING_OR_NEAR_EMA20 = "ENTRY_TOUCHING_OR_NEAR_EMA20"
    ENTRY_TOO_EXTENDED_ABOVE_EMA20 = "ENTRY_TOO_EXTENDED_ABOVE_EMA20"
    EMA20_ENTRY_REVALIDATION_UNAVAILABLE = "EMA20_ENTRY_REVALIDATION_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class Ema20EntrySafety:
    ticker: str
    as_of: datetime
    entry_price: Decimal | None
    entry_price_source: Ema20EntryPriceSource | None
    entry_price_timestamp: datetime | None
    ema20: Decimal | None
    ema20_source: Ema20AnchorSource
    ema20_as_of: date | None
    distance_to_ema20: Decimal | None
    distance_to_ema20_pct: Decimal | None
    relation: Ema20EntryRelation
    status: Ema20EntrySafetyStatus
    reason: Ema20EntrySafetyReason
    policy_version: str = "ema20-entry-safety-v1"
    upper_bound_multiplier: Decimal = EMA20_PULLBACK_UPPER_BOUND


def assess_ema20_entry_safety(
    *,
    ticker: str,
    as_of: datetime,
    entry_price: Decimal | None,
    entry_price_source: Ema20EntryPriceSource | None,
    entry_price_timestamp: datetime | None,
    ema20: Decimal | None,
    ema20_as_of: date | None,
    entry_price_is_fresh: bool = True,
) -> Ema20EntrySafety:
    unavailable = (
        entry_price is None
        or entry_price <= 0
        or entry_price_source is None
        or entry_price_timestamp is None
        or ema20 is None
        or ema20 <= 0
        or ema20_as_of is None
        or not entry_price_is_fresh
    )
    if unavailable:
        return Ema20EntrySafety(
            ticker.upper(),
            as_of,
            entry_price,
            entry_price_source,
            entry_price_timestamp,
            ema20,
            Ema20AnchorSource.COMPLETED_SIGNAL_SESSION_EMA20,
            ema20_as_of,
            None,
            None,
            Ema20EntryRelation.UNAVAILABLE,
            Ema20EntrySafetyStatus.UNAVAILABLE,
            Ema20EntrySafetyReason.EMA20_ENTRY_REVALIDATION_UNAVAILABLE,
        )
    assert entry_price is not None
    assert ema20 is not None
    distance = entry_price - ema20
    distance_pct = distance / ema20 * Decimal("100")
    if entry_price < ema20:
        relation = Ema20EntryRelation.BELOW
        status = Ema20EntrySafetyStatus.ELIGIBLE
        reason = Ema20EntrySafetyReason.ENTRY_BELOW_EMA20
    elif entry_price <= ema20 * EMA20_PULLBACK_UPPER_BOUND:
        relation = Ema20EntryRelation.TOUCHING_OR_NEAR
        status = Ema20EntrySafetyStatus.ELIGIBLE
        reason = Ema20EntrySafetyReason.ENTRY_TOUCHING_OR_NEAR_EMA20
    else:
        relation = Ema20EntryRelation.EXTENDED_ABOVE
        status = Ema20EntrySafetyStatus.BLOCKED
        reason = Ema20EntrySafetyReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20
    return Ema20EntrySafety(
        ticker.upper(),
        as_of,
        entry_price,
        entry_price_source,
        entry_price_timestamp,
        ema20,
        Ema20AnchorSource.COMPLETED_SIGNAL_SESSION_EMA20,
        ema20_as_of,
        distance,
        distance_pct,
        relation,
        status,
        reason,
    )
