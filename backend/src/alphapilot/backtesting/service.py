from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol
from uuid import UUID

from alphapilot.backtesting.benchmark import (
    BuyAndHoldSimulator,
)
from alphapilot.backtesting.diagnostics import (
    BacktestDiagnostics,
    BacktestDiagnosticsCalculator,
)
from alphapilot.backtesting.engine import BacktestingEngine
from alphapilot.backtesting.metrics import (
    PerformanceMetrics,
    PerformanceMetricsCalculator,
)
from alphapilot.backtesting.models import (
    BacktestResult,
    PortfolioConfig,
    PortfolioSimulationResult,
    TradeSimulationResult,
)
from alphapilot.backtesting.portfolio import PortfolioSimulator
from alphapilot.backtesting.portfolio_metrics import (
    PortfolioPerformanceMetrics,
    PortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.simulator import TradeSimulator
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.base import TradingStrategy


class CompanyLookupService(Protocol):
    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        """Return a company by ticker."""


class CandleHistoryService(Protocol):
    async def get_history(
        self,
        company_id: UUID,
        start: date,
        end: date,
    ) -> list[DailyCandle]:
        """Return historical daily candles."""


@dataclass(slots=True, frozen=True)
class BacktestRunResult:
    """Complete result of one historical strategy run."""

    backtest: BacktestResult
    simulation: TradeSimulationResult

    portfolio: PortfolioSimulationResult
    metrics: PerformanceMetrics
    portfolio_metrics: PortfolioPerformanceMetrics

    buy_and_hold: PortfolioSimulationResult
    buy_and_hold_metrics: PortfolioPerformanceMetrics

    spy_buy_and_hold: PortfolioSimulationResult
    spy_buy_and_hold_metrics: PortfolioPerformanceMetrics

    diagnostics: BacktestDiagnostics


class BacktestService:
    """Loads historical data and runs a complete backtest."""

    STOCK_WARMUP_DAYS = 120
    MARKET_WARMUP_DAYS = 400

    MARKET_BENCHMARK_TICKER = "SPY"

    def __init__(
        self,
        company_service: CompanyLookupService,
        candle_service: CandleHistoryService,
        strategy: TradingStrategy,
        stock_warmup_days: int = STOCK_WARMUP_DAYS,
    ) -> None:
        if stock_warmup_days <= 0:
            raise ValueError("stock_warmup_days must be greater than zero")

        self.company_service = company_service
        self.candle_service = candle_service
        self.strategy = strategy
        self.stock_warmup_days = stock_warmup_days

    async def run(
        self,
        ticker: str,
        start: date,
        end: date,
        *,
        portfolio_config: PortfolioConfig | None = None,
    ) -> BacktestRunResult:
        if start > end:
            raise ValueError("start must be before or equal to end")

        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise ValueError("ticker must not be empty")

        company = await self.company_service.get_company(normalized_ticker)

        if company is None:
            raise ValueError(f"Company {normalized_ticker} not found")

        benchmark_company = await self.company_service.get_company(self.MARKET_BENCHMARK_TICKER)

        if benchmark_company is None:
            raise RuntimeError("SPY benchmark company not found")

        stock_history_start = start - timedelta(
            days=self.stock_warmup_days,
        )

        market_history_start = start - timedelta(
            days=self.MARKET_WARMUP_DAYS,
        )

        stock_candles = await self.candle_service.get_history(
            company.id,
            stock_history_start,
            end,
        )

        benchmark_candles = await self.candle_service.get_history(
            benchmark_company.id,
            market_history_start,
            end,
        )

        if not stock_candles:
            raise RuntimeError(f"No historical candles found for {normalized_ticker}")

        if not benchmark_candles:
            raise RuntimeError("No historical candles found for SPY")

        engine = BacktestingEngine(self.strategy)

        backtest = engine.run(
            company=company,
            candles=stock_candles,
            benchmark_ticker=(self.MARKET_BENCHMARK_TICKER),
            benchmark_candles=benchmark_candles,
            start=start,
            end=end,
        )

        trade_simulator = TradeSimulator()

        simulation = trade_simulator.run(backtest)

        metrics_calculator = PerformanceMetricsCalculator()

        metrics = metrics_calculator.calculate(simulation)

        portfolio_simulator = PortfolioSimulator(portfolio_config)

        portfolio = portfolio_simulator.run(backtest)

        portfolio_metrics_calculator = PortfolioPerformanceMetricsCalculator()

        portfolio_metrics = portfolio_metrics_calculator.calculate(portfolio)

        benchmark_simulator = BuyAndHoldSimulator()

        buy_and_hold = benchmark_simulator.run(
            ticker=company.ticker,
            candles=stock_candles,
            start=start,
            end=end,
            config=portfolio_config,
        )

        spy_buy_and_hold = benchmark_simulator.run(
            ticker=self.MARKET_BENCHMARK_TICKER,
            candles=benchmark_candles,
            start=start,
            end=end,
            config=portfolio_config,
        )

        buy_and_hold_metrics = portfolio_metrics_calculator.calculate(buy_and_hold)

        spy_buy_and_hold_metrics = portfolio_metrics_calculator.calculate(spy_buy_and_hold)

        diagnostics_calculator = BacktestDiagnosticsCalculator()

        diagnostics = diagnostics_calculator.calculate(
            backtest,
            portfolio,
            stock_candles,
        )

        return BacktestRunResult(
            backtest=backtest,
            simulation=simulation,
            portfolio=portfolio,
            metrics=metrics,
            portfolio_metrics=portfolio_metrics,
            buy_and_hold=buy_and_hold,
            buy_and_hold_metrics=(buy_and_hold_metrics),
            spy_buy_and_hold=(spy_buy_and_hold),
            spy_buy_and_hold_metrics=(spy_buy_and_hold_metrics),
            diagnostics=diagnostics,
        )
