from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from alphapilot.backtesting.benchmark import BuyAndHoldSimulator
from alphapilot.backtesting.candidate_selection import (
    CandidateSelectionPolicy,
    TickerAscendingSelectionPolicy,
)
from alphapilot.backtesting.engine import BacktestingEngine
from alphapilot.backtesting.models import PortfolioConfig, PortfolioSimulationResult
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetrics,
    MultiPortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioConfig,
    MultiPortfolioSimulationResult,
)
from alphapilot.backtesting.portfolio_metrics import (
    PortfolioPerformanceMetrics,
    PortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.service import CandleHistoryService, CompanyLookupService
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.strategy.base import TradingStrategy


@dataclass(slots=True, frozen=True)
class MultiPortfolioRunResult:
    portfolio: MultiPortfolioSimulationResult
    metrics: MultiPortfolioPerformanceMetrics
    spy_buy_and_hold: PortfolioSimulationResult
    spy_metrics: PortfolioPerformanceMetrics
    successful_tickers: tuple[str, ...]
    failed_tickers: tuple[tuple[str, str], ...]
    selection_policy_name: str


class MultiPortfolioBacktestService:
    SP500_INDEX_SYMBOL = "^GSPC"
    MARKET_BENCHMARK_TICKER = "SPY"
    MARKET_WARMUP_DAYS = 400

    def __init__(
        self,
        company_service: CompanyLookupService,
        candle_service: CandleHistoryService,
        universe_repository: IndexConstituentRepository,
        strategy: TradingStrategy,
        *,
        stock_warmup_days: int,
        selection_policy: CandidateSelectionPolicy | None = None,
    ) -> None:
        if stock_warmup_days <= 0:
            raise ValueError("stock_warmup_days must be greater than zero")

        self.company_service = company_service
        self.candle_service = candle_service
        self.universe_repository = universe_repository
        self.strategy = strategy
        self.stock_warmup_days = stock_warmup_days
        self.selection_policy = (
            selection_policy if selection_policy is not None else TickerAscendingSelectionPolicy()
        )

    async def run(
        self,
        *,
        start: date,
        end: date,
        config: MultiPortfolioConfig,
    ) -> MultiPortfolioRunResult:
        if start > end:
            raise ValueError("start must be before or equal to end")

        benchmark_company = await self.company_service.get_company(self.MARKET_BENCHMARK_TICKER)

        if benchmark_company is None:
            raise RuntimeError("SPY benchmark company not found")

        benchmark_candles = await self.candle_service.get_history(
            benchmark_company.id,
            start - timedelta(days=self.MARKET_WARMUP_DAYS),
            end,
        )

        if not benchmark_candles:
            raise RuntimeError("No historical candles found for SPY")

        constituents = await self.universe_repository.list_active(self.SP500_INDEX_SYMBOL)
        tickers = sorted({item.ticker.upper() for item in constituents})
        engine = BacktestingEngine(self.strategy)
        backtests = {}
        successful: list[str] = []
        failed: list[tuple[str, str]] = []

        for ticker in tickers:
            try:
                company = await self.company_service.get_company(ticker)

                if company is None:
                    raise ValueError(f"Company {ticker} not found")

                candles = await self.candle_service.get_history(
                    company.id,
                    start - timedelta(days=self.stock_warmup_days),
                    end,
                )

                if not candles:
                    raise RuntimeError(f"No historical candles found for {ticker}")

                backtests[ticker] = engine.run(
                    company=company,
                    candles=candles,
                    benchmark_ticker=self.MARKET_BENCHMARK_TICKER,
                    benchmark_candles=benchmark_candles,
                    start=start,
                    end=end,
                )
                successful.append(ticker)
            except Exception as exc:
                failed.append((ticker, f"{type(exc).__name__}: {exc}"))

        portfolio = MultiPortfolioSimulator(
            config=config,
            selection_policy=self.selection_policy,
        ).run(backtests)
        metrics = MultiPortfolioPerformanceMetricsCalculator().calculate(portfolio)

        benchmark_config = PortfolioConfig(
            initial_capital=config.initial_capital,
            position_size_pct=Decimal("100"),
            commission_per_order=config.commission_per_order,
            slippage_bps=config.slippage_bps,
        )
        spy = BuyAndHoldSimulator().run(
            ticker=self.MARKET_BENCHMARK_TICKER,
            candles=benchmark_candles,
            start=(portfolio.equity_curve[0].trading_day if portfolio.equity_curve else start),
            end=(portfolio.equity_curve[-1].trading_day if portfolio.equity_curve else end),
            config=benchmark_config,
        )
        spy_metrics = PortfolioPerformanceMetricsCalculator().calculate(spy)

        return MultiPortfolioRunResult(
            portfolio=portfolio,
            metrics=metrics,
            spy_buy_and_hold=spy,
            spy_metrics=spy_metrics,
            successful_tickers=tuple(successful),
            failed_tickers=tuple(failed),
            selection_policy_name=self.selection_policy.name,
        )
