from datetime import date
from uuid import UUID

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.services.base import BaseService


class DailyCandleService(BaseService[DailyCandleRepository]):
    def __init__(
        self,
        repository: DailyCandleRepository,
    ) -> None:
        super().__init__(repository)

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
