from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from alphapilot.database.models.daily_candle import DailyCandle


@dataclass(slots=True, frozen=True)
class PortfolioRiskConfig:
    risk_per_position_pct: Decimal = Decimal("1")
    atr_period: int = 14
    atr_stop_multiple: Decimal = Decimal("2")
    max_position_weight_pct: Decimal = Decimal("10")
    max_portfolio_risk_pct: Decimal = Decimal("8")
    minimum_cash_reserve_pct: Decimal = Decimal("10")
    max_sector_weight_pct: Decimal = Decimal("30")
    max_positions: int = 10

    def __post_init__(self) -> None:
        for name in (
            "risk_per_position_pct",
            "atr_stop_multiple",
            "max_position_weight_pct",
            "max_portfolio_risk_pct",
            "max_sector_weight_pct",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if not Decimal("0") <= self.minimum_cash_reserve_pct < Decimal("100"):
            raise ValueError("minimum_cash_reserve_pct must be between 0 and 100")
        if self.atr_period <= 0 or self.max_positions <= 0:
            raise ValueError("atr_period and max_positions must be greater than zero")


class AverageTrueRangeCalculator:
    def true_range(self, candle: DailyCandle, previous_close: Decimal) -> Decimal:
        return max(
            candle.high - candle.low,
            abs(candle.high - previous_close),
            abs(candle.low - previous_close),
        )

    def calculate(
        self,
        candles: list[DailyCandle],
        *,
        signal_day: date,
        period: int = 14,
    ) -> Decimal | None:
        available = sorted(
            (candle for candle in candles if candle.trading_day <= signal_day),
            key=lambda candle: candle.trading_day,
        )
        if period <= 0 or len(available) < period + 1:
            return None
        selected = available[-(period + 1) :]
        ranges = [
            self.true_range(current, previous.close)
            for previous, current in zip(selected, selected[1:], strict=False)
        ]
        atr = sum(ranges, Decimal("0")) / Decimal(period)
        return atr if atr > 0 else None
