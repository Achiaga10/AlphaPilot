from datetime import date

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.providers.base import MarketProvider
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService


class MarketSyncService:
    def __init__(
        self,
        provider: MarketProvider,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.company_service = company_service
        self.candle_service = candle_service
        self.session_policy = session_policy or CompletedDailySessionPolicy()

    async def sync_company(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> bool:
        company = await self.company_service.get_company(ticker)

        if company is None:
            return False

        market_candles = await self.provider.get_history(
            company.ticker,
            start,
            end,
        )

        candles = [
            DailyCandle(
                company_id=company.id,
                trading_day=candle.date,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
            for candle in market_candles
            if self.session_policy.is_complete(candle.date)
        ]

        if not candles:
            return False
        await self.candle_service.upsert_many(candles)

        return True
