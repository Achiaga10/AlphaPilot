from datetime import date
from decimal import Decimal
from uuid import UUID

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.daily_candle import DailyCandleRepository


class DailyCandleService:
    def __init__(
        self,
        repository: DailyCandleRepository,
    ) -> None:
        self.repository = repository

    async def create(
        self,
        company_id: UUID,
        trading_day: date,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: int,
    ) -> DailyCandle:
        candle = DailyCandle(
            company_id=company_id,
            trading_day=trading_day,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

        return await self.repository.create(candle)

    async def get_history(
        self,
        company_id: UUID,
        start: date,
        end: date,
    ) -> list[DailyCandle]:
        return await self.repository.get_history(
            company_id,
            start,
            end,
        )

    async def upsert_many(
        self,
        candles: list[DailyCandle],
    ) -> None:
        await self.repository.upsert_many(candles)
