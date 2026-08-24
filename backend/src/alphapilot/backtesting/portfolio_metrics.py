from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, stdev

from alphapilot.backtesting.models import PortfolioSimulationResult


@dataclass(slots=True, frozen=True)
class PortfolioPerformanceMetrics:
    """Performance metrics calculated from an equity curve."""

    final_equity: Decimal
    total_return_pct: Decimal

    cagr_pct: Decimal | None
    max_drawdown_pct: Decimal

    sharpe_ratio: Decimal | None
    exposure_pct: Decimal

    completed_trades: int
    average_holding_days: Decimal | None


class PortfolioPerformanceMetricsCalculator:
    """Calculates portfolio-level performance statistics."""

    CALENDAR_DAYS_PER_YEAR = 365.25
    TRADING_DAYS_PER_YEAR = 252

    def calculate(
        self,
        portfolio: PortfolioSimulationResult,
    ) -> PortfolioPerformanceMetrics:
        return PortfolioPerformanceMetrics(
            final_equity=portfolio.final_equity,
            total_return_pct=portfolio.total_return_pct,
            cagr_pct=self._calculate_cagr(portfolio),
            max_drawdown_pct=(self._calculate_max_drawdown(portfolio)),
            sharpe_ratio=self._calculate_sharpe(portfolio),
            exposure_pct=self._calculate_exposure(portfolio),
            completed_trades=len(portfolio.trades),
            average_holding_days=(self._calculate_average_holding_days(portfolio)),
        )

    def _calculate_cagr(
        self,
        portfolio: PortfolioSimulationResult,
    ) -> Decimal | None:
        if len(portfolio.equity_curve) < 2:
            return None

        first_day = portfolio.equity_curve[0].trading_day

        last_day = portfolio.equity_curve[-1].trading_day

        elapsed_days = (last_day - first_day).days

        if elapsed_days <= 0:
            return None

        if portfolio.initial_capital <= 0:
            return None

        if portfolio.final_equity <= 0:
            return None

        years = elapsed_days / self.CALENDAR_DAYS_PER_YEAR

        growth_multiple = float(portfolio.final_equity / portfolio.initial_capital)

        cagr = (growth_multiple ** (1 / years) - 1) * 100

        return Decimal(str(cagr))

    @staticmethod
    def _calculate_max_drawdown(
        portfolio: PortfolioSimulationResult,
    ) -> Decimal:
        if not portfolio.equity_curve:
            return Decimal("0")

        peak = portfolio.equity_curve[0].equity

        maximum_drawdown = Decimal("0")

        for point in portfolio.equity_curve:
            if point.equity > peak:
                peak = point.equity

            if peak <= 0:
                continue

            drawdown = (peak - point.equity) / peak * Decimal("100")

            maximum_drawdown = max(
                maximum_drawdown,
                drawdown,
            )

        return maximum_drawdown

    def _calculate_sharpe(
        self,
        portfolio: PortfolioSimulationResult,
    ) -> Decimal | None:
        equity_curve = portfolio.equity_curve

        if len(equity_curve) < 3:
            return None

        daily_returns: list[float] = []

        for previous, current in zip(
            equity_curve,
            equity_curve[1:],
            strict=False,
        ):
            if previous.equity == 0:
                continue

            daily_return = float((current.equity - previous.equity) / previous.equity)

            daily_returns.append(daily_return)

        if len(daily_returns) < 2:
            return None

        volatility = stdev(daily_returns)

        if volatility == 0:
            return None

        average_daily_return = mean(daily_returns)

        sharpe = average_daily_return / volatility * sqrt(self.TRADING_DAYS_PER_YEAR)

        return Decimal(str(sharpe))

    @staticmethod
    def _calculate_exposure(
        portfolio: PortfolioSimulationResult,
    ) -> Decimal:
        if not portfolio.equity_curve:
            return Decimal("0")

        invested_days = sum(1 for point in portfolio.equity_curve if point.shares > 0)

        return Decimal(invested_days) / Decimal(len(portfolio.equity_curve)) * Decimal("100")

    @staticmethod
    def _calculate_average_holding_days(
        portfolio: PortfolioSimulationResult,
    ) -> Decimal | None:
        if not portfolio.trades:
            return None

        total_days = sum((trade.exit_day - trade.entry_day).days for trade in portfolio.trades)

        return Decimal(total_days) / Decimal(len(portfolio.trades))
