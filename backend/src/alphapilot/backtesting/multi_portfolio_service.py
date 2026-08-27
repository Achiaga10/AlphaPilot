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
from alphapilot.backtesting.models import BacktestResult, PortfolioConfig, PortfolioSimulationResult
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetrics,
    MultiPortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioConfig,
    MultiPortfolioSimulationResult,
)
from alphapilot.backtesting.portfolio_attribution import (
    AttributionSummary,
    PortfolioAttributionCalculator,
)
from alphapilot.backtesting.portfolio_metrics import (
    PortfolioPerformanceMetrics,
    PortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.ranking_features import RelativeStrength20Calculator
from alphapilot.backtesting.service import CandleHistoryService, CompanyLookupService
from alphapilot.backtesting.trade_management import TradeManagementExitReason
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.portfolio.risk import AverageTrueRangeCalculator
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.signal import Signal


@dataclass(slots=True, frozen=True)
class MultiPortfolioRunResult:
    portfolio: MultiPortfolioSimulationResult
    metrics: MultiPortfolioPerformanceMetrics
    spy_buy_and_hold: PortfolioSimulationResult
    spy_metrics: PortfolioPerformanceMetrics
    successful_tickers: tuple[str, ...]
    failed_tickers: tuple[tuple[str, str], ...]
    selection_policy_name: str
    attribution: AttributionSummary
    exit_recovery_diagnostics: tuple[ExitRecoveryDiagnostic, ...] = ()


@dataclass(slots=True, frozen=True)
class ExitRecoveryDiagnostic:
    """Ex-post diagnostic only; never consulted by portfolio execution."""

    ticker: str
    exit_day: date
    exit_price: Decimal
    entry_price: Decimal
    return_5_sessions_pct: Decimal | None
    return_10_sessions_pct: Decimal | None
    return_20_sessions_pct: Decimal | None
    recovered_entry_price_within_20_sessions: bool | None
    later_strategy_exit_signal_day: date | None


@dataclass(slots=True, frozen=True)
class PreparedMultiPortfolioData:
    start: date
    end: date
    backtests: dict[str, BacktestResult]
    stock_histories: dict[str, list[DailyCandle]]
    benchmark_candles: list[DailyCandle]
    ticker_sectors: dict[str, str | None]
    ranking_scores: dict[tuple[str, date], Decimal | None]
    atr_values: dict[tuple[str, date], Decimal | None]
    successful_tickers: tuple[str, ...]
    failed_tickers: tuple[tuple[str, str], ...]


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
        prepared = await self.prepare(start=start, end=end)
        return self.run_prepared(prepared, config=config)

    async def prepare(self, *, start: date, end: date) -> PreparedMultiPortfolioData:
        """Load/evaluate immutable strategy data once for an exit-policy matrix."""

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
        stock_histories = {}
        ticker_sectors: dict[str, str | None] = {}
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
                stock_histories[ticker] = candles
                ticker_sectors[ticker] = company.sector
                successful.append(ticker)
            except Exception as exc:
                failed.append((ticker, f"{type(exc).__name__}: {exc}"))

        ranking_scores: dict[tuple[str, date], Decimal | None] = {}
        atr_values: dict[tuple[str, date], Decimal | None] = {}

        if self.selection_policy.uses_scores:
            calculator = RelativeStrength20Calculator()

            for ticker, backtest in backtests.items():
                for bar in backtest.bars:
                    if bar.signal != Signal.BUY:
                        continue

                    ranking_scores[(ticker, bar.trading_day)] = calculator.calculate(
                        stock_candles=stock_histories[ticker],
                        benchmark_candles=benchmark_candles,
                        signal_day=bar.trading_day,
                    )

        atr_calculator = AverageTrueRangeCalculator()
        for ticker, backtest in backtests.items():
            atr_series = atr_calculator.calculate_series(stock_histories[ticker], period=14)
            for bar in backtest.bars:
                atr_values[(ticker, bar.trading_day)] = atr_series.get(bar.trading_day)

        return PreparedMultiPortfolioData(
            start=start,
            end=end,
            backtests=backtests,
            stock_histories=stock_histories,
            benchmark_candles=benchmark_candles,
            ticker_sectors=ticker_sectors,
            ranking_scores=ranking_scores,
            atr_values=atr_values,
            successful_tickers=tuple(successful),
            failed_tickers=tuple(failed),
        )

    def run_prepared(
        self,
        prepared: PreparedMultiPortfolioData,
        *,
        config: MultiPortfolioConfig,
    ) -> MultiPortfolioRunResult:
        """Simulate one policy without reloading or regenerating strategy signals."""

        portfolio = MultiPortfolioSimulator(
            config=config,
            selection_policy=self.selection_policy,
        ).run(
            prepared.backtests,
            ranking_scores=prepared.ranking_scores,
            ticker_sectors=prepared.ticker_sectors,
            atr_values=prepared.atr_values,
        )
        metrics = MultiPortfolioPerformanceMetricsCalculator().calculate(portfolio)
        attribution = PortfolioAttributionCalculator().calculate(portfolio)

        benchmark_config = PortfolioConfig(
            initial_capital=config.initial_capital,
            position_size_pct=Decimal("100"),
            commission_per_order=config.commission_per_order,
            slippage_bps=config.slippage_bps,
        )
        spy = BuyAndHoldSimulator().run(
            ticker=self.MARKET_BENCHMARK_TICKER,
            candles=prepared.benchmark_candles,
            start=(
                portfolio.equity_curve[0].trading_day if portfolio.equity_curve else prepared.start
            ),
            end=(
                portfolio.equity_curve[-1].trading_day if portfolio.equity_curve else prepared.end
            ),
            config=benchmark_config,
        )
        spy_metrics = PortfolioPerformanceMetricsCalculator().calculate(spy)

        return MultiPortfolioRunResult(
            portfolio=portfolio,
            metrics=metrics,
            spy_buy_and_hold=spy,
            spy_metrics=spy_metrics,
            successful_tickers=prepared.successful_tickers,
            failed_tickers=prepared.failed_tickers,
            selection_policy_name=self.selection_policy.name,
            attribution=attribution,
            exit_recovery_diagnostics=self._build_exit_recovery_diagnostics(
                portfolio,
                prepared,
            ),
        )

    @staticmethod
    def _build_exit_recovery_diagnostics(
        portfolio: MultiPortfolioSimulationResult,
        prepared: PreparedMultiPortfolioData,
    ) -> tuple[ExitRecoveryDiagnostic, ...]:
        diagnostics: list[ExitRecoveryDiagnostic] = []
        stop_reasons = {
            TradeManagementExitReason.INITIAL_ATR_STOP,
            TradeManagementExitReason.ATR_TRAILING_STOP,
        }
        for trade in portfolio.trades:
            if trade.exit_reason not in stop_reasons:
                continue
            future = sorted(
                (
                    candle
                    for candle in prepared.stock_histories[trade.ticker]
                    if candle.trading_day > trade.exit_day
                ),
                key=lambda candle: candle.trading_day,
            )

            def future_return(
                session: int,
                *,
                future_candles: list[DailyCandle] = future,
                exit_price: Decimal = trade.exit_price,
            ) -> Decimal | None:
                if len(future_candles) < session or exit_price <= 0:
                    return None
                return (
                    (future_candles[session - 1].close - exit_price) / exit_price * Decimal("100")
                )

            first_twenty = future[:20]
            recovered = (
                any(candle.close >= trade.entry_price for candle in first_twenty)
                if first_twenty
                else None
            )
            later_exit = next(
                (
                    bar.trading_day
                    for bar in prepared.backtests[trade.ticker].bars
                    if bar.trading_day > trade.exit_day and bar.signal == Signal.SELL
                ),
                None,
            )
            diagnostics.append(
                ExitRecoveryDiagnostic(
                    ticker=trade.ticker,
                    exit_day=trade.exit_day,
                    exit_price=trade.exit_price,
                    entry_price=trade.entry_price,
                    return_5_sessions_pct=future_return(5),
                    return_10_sessions_pct=future_return(10),
                    return_20_sessions_pct=future_return(20),
                    recovered_entry_price_within_20_sessions=recovered,
                    later_strategy_exit_signal_day=later_exit,
                )
            )
        return tuple(diagnostics)
