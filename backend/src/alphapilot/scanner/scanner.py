from datetime import UTC, date, datetime, timedelta
from typing import Any

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.providers.base import MarketProvider
from alphapilot.repositories.index_constituent import (
    IndexConstituentRepository,
)
from alphapilot.scanner.signal_result import SignalResult
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import StrategyEvaluation
from alphapilot.strategy.signal import Signal


class Scanner:
    """Scans companies and evaluates them using a trading strategy."""

    STOCK_HISTORY_LOOKBACK_DAYS = 120
    MARKET_HISTORY_LOOKBACK_DAYS = 400

    MARKET_BENCHMARK_TICKER = "SPY"
    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        provider: MarketProvider,
        company_service: CompanyService,
        candle_service: DailyCandleService,
        strategy: TradingStrategy,
        universe_repository: IndexConstituentRepository,
    ) -> None:
        self.provider = provider
        self.company_service = company_service
        self.candle_service = candle_service
        self.strategy = strategy
        self.universe_repository = universe_repository

    async def scan_company(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        return await self.provider.get_quote(
            ticker,
        )

    async def _list_scan_companies(
        self,
    ) -> list[Company]:
        constituents = await self.universe_repository.list_active(
            self.SP500_INDEX_SYMBOL,
        )

        active_tickers = {constituent.ticker for constituent in constituents}

        companies = await self.company_service.list_companies()

        return [company for company in companies if company.ticker.upper() in active_tickers]

    async def evaluate_company(
        self,
        ticker: str,
    ) -> SignalResult | None:
        company = await self.company_service.get_company(
            ticker,
        )

        if company is None:
            return None

        end_date = date.today()

        context = await self._get_strategy_context(
            end_date,
        )

        candles = await self._get_company_candles(
            company,
            end_date,
        )

        evaluation = self.strategy.evaluate(
            company,
            candles,
            context,
        )

        return self._build_signal_result(
            company,
            candles,
            evaluation,
        )

    async def scan_all(
        self,
    ) -> list[SignalResult]:
        companies = await self._list_scan_companies()

        selected: list[SignalResult] = []

        end_date = date.today()

        context = await self._get_strategy_context(
            end_date,
        )

        for company in companies:
            if company.ticker.upper() == self.MARKET_BENCHMARK_TICKER:
                continue

            candles = await self._get_company_candles(
                company,
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
                self._build_signal_result(
                    company,
                    candles,
                    evaluation,
                )
            )

        return selected

    async def _get_strategy_context(
        self,
        end_date: date,
    ) -> StrategyContext:
        market_start_date = end_date - timedelta(
            days=self.MARKET_HISTORY_LOOKBACK_DAYS,
        )

        benchmark_company = await self.company_service.get_company(
            self.MARKET_BENCHMARK_TICKER,
        )

        benchmark_candles: list[DailyCandle] = []

        if benchmark_company is not None:
            benchmark_candles = await self.candle_service.get_history(
                benchmark_company.id,
                market_start_date,
                end_date,
            )

        return StrategyContext(
            benchmark_ticker=(self.MARKET_BENCHMARK_TICKER),
            benchmark_candles=tuple(benchmark_candles),
        )

    async def _get_company_candles(
        self,
        company: Company,
        end_date: date,
    ) -> list[DailyCandle]:
        stock_start_date = end_date - timedelta(
            days=self.STOCK_HISTORY_LOOKBACK_DAYS,
        )

        return await self.candle_service.get_history(
            company.id,
            stock_start_date,
            end_date,
        )

    def _build_signal_result(
        self,
        company: Company,
        candles: list[DailyCandle],
        evaluation: StrategyEvaluation,
    ) -> SignalResult:
        price = float(candles[-1].close) if candles else None

        ema20 = float(evaluation.ema20) if evaluation.ema20 is not None else None

        ema50 = float(evaluation.ema50) if evaluation.ema50 is not None else None

        return SignalResult(
            ticker=company.ticker,
            signal=evaluation.signal,
            price=price,
            ema20=ema20,
            ema50=ema50,
            market_regime=evaluation.market_regime,
            reason=evaluation.reason,
            generated_at=datetime.now(UTC),
        )
