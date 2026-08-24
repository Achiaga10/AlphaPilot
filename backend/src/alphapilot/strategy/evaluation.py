from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from alphapilot.strategy.signal import Signal


class MarketRegime(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class SignalReason(Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

    SMA20_CROSS_UP = "SMA20_CROSS_UP"
    SMA20_CROSS_DOWN = "SMA20_CROSS_DOWN"
    NO_SMA20_CROSS = "NO_SMA20_CROSS"

    TREND_BREAKDOWN = "TREND_BREAKDOWN"
    EMA20_TREND_BREAKDOWN = "EMA20_TREND_BREAKDOWN"

    MARKET_REGIME_BLOCKED = "MARKET_REGIME_BLOCKED"
    STOCK_TREND_NOT_BULLISH = "STOCK_TREND_NOT_BULLISH"
    NO_PULLBACK = "NO_PULLBACK"
    PULLBACK_NOT_CONFIRMED = "PULLBACK_NOT_CONFIRMED"

    EMA20_PULLBACK_RECLAIM = "EMA20_PULLBACK_RECLAIM"

    MICHO_150_BREAKOUT = "MICHO_150_BREAKOUT"
    MICHO_150_BOUNCE = "MICHO_150_BOUNCE"
    MICHO_150_BREAKDOWN = "MICHO_150_BREAKDOWN"
    MICHO_150_TREND_NOT_READY = "MICHO_150_TREND_NOT_READY"
    MICHO_150_NO_ENTRY = "MICHO_150_NO_ENTRY"


@dataclass(slots=True, frozen=True)
class StrategyEvaluation:
    signal: Signal
    reason: SignalReason

    ema20: Decimal | None = None
    ema50: Decimal | None = None

    market_regime: MarketRegime = MarketRegime.UNKNOWN

    sma150: Decimal | None = None
