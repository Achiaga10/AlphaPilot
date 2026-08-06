from dataclasses import dataclass
from datetime import datetime

from alphapilot.strategy.signal import Signal


@dataclass(slots=True)
class SignalResult:
    ticker: str
    signal: Signal
    price: float
    generated_at: datetime
