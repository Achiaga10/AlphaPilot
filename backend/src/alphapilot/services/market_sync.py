from datetime import UTC, date, datetime

from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.market_data_ingestion import CandleProvenanceStatus
from alphapilot.market.provenance import CandleVersionProvenance
from alphapilot.market.providers.base import MarketProvider
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService


class MarketSyncService:
    def __init__(
        self,
        provider: MarketProvider,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        ingestion_batch_service: MarketDataIngestionBatchService,
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.company_service = company_service
        self.candle_service = candle_service
        self.ingestion_batch_service = ingestion_batch_service
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

        provider_name = str(getattr(self.provider, "provider_name", "unknown")).lower()
        provider_feed = getattr(self.provider, "feed", None)
        feed = str(getattr(provider_feed, "value", provider_feed) or "unknown").lower()
        batch = await self.ingestion_batch_service.start(
            provider=provider_name,
            feed=feed,
            timeframe=str(getattr(self.provider, "timeframe", "1Day")),
            adjustment=str(getattr(self.provider, "adjustment", "unknown")),
            requested_start=start,
            requested_end=end,
            symbols_requested=1,
            benchmark_ticker=("SPY" if company.ticker.upper() == "SPY" else None),
            request_metadata={},
        )
        try:
            market_candles = await self.provider.get_history(
                company.ticker,
                start,
                end,
            )
        except Exception:
            await self.ingestion_batch_service.fail(batch, failed=1)
            raise

        try:
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
                await self.ingestion_batch_service.complete(batch, succeeded=0, failed=0)
                return False
            await self.candle_service.upsert_many(
                candles,
                provenance=CandleVersionProvenance(
                    provider=provider_name,
                    feed=feed,
                    ingestion_batch_id=batch.id,
                    observed_at=datetime.now(UTC),
                    status=CandleProvenanceStatus.COMPLETE,
                ),
            )
            await self.ingestion_batch_service.complete(batch, succeeded=1, failed=0)
        except Exception:
            await self.ingestion_batch_service.fail_after_error(batch.id, failed=1)
            raise

        return True
