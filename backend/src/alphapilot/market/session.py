from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(slots=True, frozen=True)
class CompletedDailySessionPolicy:
    """Conservative completion boundary for U.S. daily research bars.

    Stored SPY dates remain the trading-session calendar. The clock rule only
    quarantines the current New York date until after the regular close plus a
    short provider-finalization buffer. Early-close sessions are intentionally
    delayed until this conservative boundary rather than guessed.
    """

    now_provider: Callable[[], datetime] = lambda: datetime.now(UTC)

    MARKET_TIME_ZONE = ZoneInfo("America/New_York")
    COMPLETED_AFTER = time(16, 15)

    def completed_through(self) -> date:
        market_now = self.now_provider().astimezone(self.MARKET_TIME_ZONE)
        if market_now.time() >= self.COMPLETED_AFTER:
            return market_now.date()
        return market_now.date() - timedelta(days=1)

    def is_complete(self, trading_day: date) -> bool:
        return trading_day <= self.completed_through()
