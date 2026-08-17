from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from alphapilot.strategy.signal import Signal


class SignalResponse(BaseModel):
    ticker: str
    signal: Signal
    price: float
    generated_at: datetime
