from datetime import UTC, date, datetime, timedelta
from typing import Any

from alphapilot.market.providers.base import MarketProvider
from alphapilot.scanner.signal_result import SignalResult
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.signal import Signal


class Scanner:
    """Scans companies and evaluates them using a trading strategy."""

    STOCK_HISTORY_LOOKBACK_DAYS = 120
    MARKET_HISTORY_LOOKBACK_DAYS = 400

    MARKET_BENCHMARK_TICKER = "SPY"

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

        end_date = date.today()

        stock_start_date = end_date - timedelta(
            days=self.STOCK_HISTORY_LOOKBACK_DAYS,
        )

        market_start_date = end_date - timedelta(
            days=self.MARKET_HISTORY_LOOKBACK_DAYS,
        )

        benchmark_company = await self.company_service.get_company(
            self.MARKET_BENCHMARK_TICKER,
        )

        benchmark_candles = []

        if benchmark_company is not None:
            benchmark_candles = await self.candle_service.get_history(
                benchmark_company.id,
                market_start_date,
                end_date,
            )

        context = StrategyContext(
            benchmark_ticker=self.MARKET_BENCHMARK_TICKER,
            benchmark_candles=tuple(benchmark_candles),
        )

        for company in companies:
            if company.ticker.upper() == self.MARKET_BENCHMARK_TICKER:
                continue

            candles = await self.candle_service.get_history(
                company.id,
                stock_start_date,
                end_date,
            )

            evaluation = self.strategy.evaluate(
                company,
                candles,
                context,
            )

            if evaluation.signal != Signal.BUY:
                continue

            selected.append(
                SignalResult(
                    ticker=company.ticker,
                    signal=evaluation.signal,
                    price=float(candles[-1].close),
                    ema20=(float(evaluation.ema20) if evaluation.ema20 is not None else None),
                    ema50=(float(evaluation.ema50) if evaluation.ema50 is not None else None),
                    market_regime=(evaluation.market_regime),
                    reason=evaluation.reason,
                    generated_at=datetime.now(UTC),
                )
            )

        return selected
