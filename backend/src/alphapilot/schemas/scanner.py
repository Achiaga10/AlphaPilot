from datetime import datetime

from pydantic import BaseModel

from alphapilot.strategy.signal import Signal


class ScannerSignalResponse(BaseModel):
    """Trading signal returned by the market scanner."""

    ticker: str
    signal: Signal
    price: float
    generated_at: datetime
