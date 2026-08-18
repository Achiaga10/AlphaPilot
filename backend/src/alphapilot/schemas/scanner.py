from datetime import datetime

from pydantic import BaseModel

from alphapilot.strategy.evaluation import (
    MarketRegime,
    SignalReason,
)
from alphapilot.strategy.signal import Signal


class ScannerSignalResponse(BaseModel):
    """Trading signal returned by the market scanner."""

    ticker: str
    signal: Signal
    price: float | None

    ema20: float | None
    ema50: float | None

    market_regime: MarketRegime
    reason: SignalReason

    generated_at: datetime
