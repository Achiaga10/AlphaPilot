from dataclasses import dataclass
from datetime import datetime

from alphapilot.strategy.evaluation import (
    MarketRegime,
    SignalReason,
)
from alphapilot.strategy.signal import Signal


@dataclass(slots=True)
class SignalResult:
    ticker: str
    signal: Signal
    price: float | None

    ema20: float | None
    ema50: float | None

    market_regime: MarketRegime
    reason: SignalReason

    generated_at: datetime
