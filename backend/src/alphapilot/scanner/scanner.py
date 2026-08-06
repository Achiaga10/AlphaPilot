from datetime import date, datetime, timedelta
from typing import Any

from alphapilot.market.providers.base import MarketProvider
from alphapilot.scanner.signal_result import SignalResult
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.signal import Signal


class Scanner:
    """Scans companies and evaluates them using a trading strategy."""

    def __init__(
        self,
        provider: MarketProvider,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        strategy: TradingStrategy,
    ) -> None:
        self.provider = provider
        self.company_service = company_service
        self.candle_service = candle_service
        self.strategy = strategy

    async def scan_company(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        return await self.provider.get_quote(ticker)

    async def scan_all(
        self,
    ) -> list[SignalResult]:
        companies = await self.company_service.list_companies()

        selected: list[SignalResult] = []

        for company in companies:
            candles = await self.candle_service.get_history(
                company.id,
                date.today() - timedelta(days=40),
                date.today(),
            )

            signal = self.strategy.generate_signal(
                company,
                candles,
            )

            if signal == Signal.BUY:
                selected.append(
                    SignalResult(
                        ticker=company.ticker,
                        signal=signal,
                        price=float(candles[-1].close),
                        generated_at=datetime.utcnow(),
                    )
                )

        return selected
