from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.base import BaseRepository


class DailyCandleRepository(BaseRepository[DailyCandle]):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(
            session,
            DailyCandle,
        )

    async def get_history(
        self,
        company_id: UUID,
        start: date,
        end: date,
    ) -> list[DailyCandle]:
        result = await self.session.execute(
            select(DailyCandle)
            .where(
                DailyCandle.company_id == company_id,
                DailyCandle.date >= start,
                DailyCandle.date <= end,
            )
            .order_by(
                DailyCandle.date,
            )
        )

        return list(result.scalars().all())
