from datetime import date
from decimal import Decimal
from uuid import UUID

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.provenance import CandleUpsertResult, CandleVersionProvenance
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.services.company import CompanyService


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
        if not self.repository.session_policy.is_complete(trading_day):
            raise ValueError("Daily candle does not represent a completed market session")
        candle = DailyCandle(
            company_id=company_id,
            trading_day=trading_day,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

        await self.repository.upsert_many([candle])
        created = await self.repository.get_for_day(company_id, trading_day)
        if created is None:
            raise RuntimeError("Completed daily candle was not persisted")
        return created

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

    async def get_histories(
        self,
        company_ids: list[UUID],
        start: date,
        end: date,
    ) -> dict[UUID, list[DailyCandle]]:
        return await self.repository.get_histories(company_ids, start, end)

    async def upsert_many(
        self,
        candles: list[DailyCandle],
        *,
        provenance: CandleVersionProvenance | None = None,
    ) -> CandleUpsertResult:
        return await self.repository.upsert_many(candles, provenance=provenance)


class LatestStoredPriceService:
    def __init__(
        self,
        company_service: CompanyService,
        candle_repository: DailyCandleRepository,
    ) -> None:
        self.company_service = company_service
        self.candle_repository = candle_repository

    async def get_latest_stored_price(self, ticker: str) -> tuple[Decimal, date] | None:
        company = await self.company_service.get_company(ticker.strip().upper())
        if company is None:
            return None
        candle = await self.candle_repository.get_latest(company.id)
        if candle is None:
            return None
        return candle.close, candle.trading_day
