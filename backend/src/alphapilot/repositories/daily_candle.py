from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.base import BaseRepository


class DailyCandleRepository(BaseRepository[DailyCandle]):
    UPSERT_CHUNK_SIZE = 1000

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
                DailyCandle.trading_day >= start,
                DailyCandle.trading_day <= end,
            )
            .order_by(DailyCandle.trading_day),
        )

        return list(result.scalars().all())

    async def upsert_many(
        self,
        candles: list[DailyCandle],
    ) -> None:
        if not candles:
            return

        values = [
            {
                "company_id": candle.company_id,
                "trading_day": candle.trading_day,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]

        for chunk_start in range(
            0,
            len(values),
            self.UPSERT_CHUNK_SIZE,
        ):
            chunk = values[chunk_start : chunk_start + self.UPSERT_CHUNK_SIZE]

            statement = insert(DailyCandle).values(chunk)

            statement = statement.on_conflict_do_update(
                index_elements=[
                    DailyCandle.company_id,
                    DailyCandle.trading_day,
                ],
                set_={
                    "open": statement.excluded.open,
                    "high": statement.excluded.high,
                    "low": statement.excluded.low,
                    "close": statement.excluded.close,
                    "volume": statement.excluded.volume,
                },
            )

            await self.session.execute(statement)

        await self.session.commit()
