from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, stdev

from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioSimulationResult,
)


@dataclass(slots=True, frozen=True)
class MultiPortfolioPerformanceMetrics:
    initial_equity: Decimal
    final_equity: Decimal
    total_return_pct: Decimal
    cagr_pct: Decimal | None
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal | None
    exposure_pct: Decimal
    completed_trades: int
    win_rate_pct: Decimal
    profit_factor: Decimal | None
    average_trade_pct: Decimal | None
    turnover_pct: Decimal
    average_open_positions: Decimal
    max_concurrent_positions: int
    calmar_ratio: Decimal | None = None
    median_trade_pct: Decimal | None = None
    average_holding_days: Decimal | None = None
    worst_trade_pct: Decimal | None = None
    fifth_percentile_trade_pct: Decimal | None = None
    median_mae_pct: Decimal | None = None
    median_mfe_pct: Decimal | None = None
    median_giveback_pct: Decimal | None = None


class MultiPortfolioPerformanceMetricsCalculator:
    CALENDAR_DAYS_PER_YEAR = 365.25
    TRADING_DAYS_PER_YEAR = 252

    def calculate(
        self,
        portfolio: MultiPortfolioSimulationResult,
    ) -> MultiPortfolioPerformanceMetrics:
        returns = [trade.return_pct for trade in portfolio.trades]
        winning = [value for value in returns if value > 0]
        gross_profit = sum((trade.pnl for trade in portfolio.trades if trade.pnl > 0), Decimal("0"))
        gross_loss = abs(
            sum((trade.pnl for trade in portfolio.trades if trade.pnl < 0), Decimal("0"))
        )

        cagr = self._cagr(portfolio)
        drawdown = self._max_drawdown(portfolio)
        return MultiPortfolioPerformanceMetrics(
            initial_equity=portfolio.initial_capital,
            final_equity=portfolio.final_equity,
            total_return_pct=portfolio.total_return_pct,
            cagr_pct=cagr,
            max_drawdown_pct=drawdown,
            sharpe_ratio=self._sharpe(portfolio),
            exposure_pct=self._exposure(portfolio),
            completed_trades=len(portfolio.trades),
            win_rate_pct=(
                Decimal(len(winning)) / Decimal(len(returns)) * Decimal("100")
                if returns
                else Decimal("0")
            ),
            profit_factor=(gross_profit / gross_loss if gross_loss > 0 else None),
            average_trade_pct=(
                sum(returns, Decimal("0")) / Decimal(len(returns)) if returns else None
            ),
            turnover_pct=self._turnover(portfolio),
            average_open_positions=self._average_positions(portfolio),
            max_concurrent_positions=max(
                (point.open_positions for point in portfolio.equity_curve),
                default=0,
            ),
            calmar_ratio=(cagr / drawdown if cagr is not None and drawdown > 0 else None),
            median_trade_pct=self._median(returns),
            average_holding_days=(
                sum((Decimal(trade.holding_days) for trade in portfolio.trades), Decimal("0"))
                / Decimal(len(portfolio.trades))
                if portfolio.trades
                else None
            ),
            worst_trade_pct=min(returns) if returns else None,
            fifth_percentile_trade_pct=self._percentile(returns, Decimal("0.05")),
            median_mae_pct=self._median([trade.mae_pct for trade in portfolio.trades]),
            median_mfe_pct=self._median([trade.mfe_pct for trade in portfolio.trades]),
            median_giveback_pct=self._median(
                [trade.peak_giveback_pct for trade in portfolio.trades]
            ),
        )

    @staticmethod
    def _median(values: list[Decimal]) -> Decimal | None:
        if not values:
            return None
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / Decimal("2")

    @staticmethod
    def _percentile(values: list[Decimal], quantile: Decimal) -> Decimal | None:
        if not values:
            return None
        ordered = sorted(values)
        index = int(quantile * Decimal(len(ordered) - 1))
        return ordered[index]

    def _cagr(
        self,
        portfolio: MultiPortfolioSimulationResult,
    ) -> Decimal | None:
        if len(portfolio.equity_curve) < 2 or portfolio.final_equity <= 0:
            return None

        elapsed_days = (
            portfolio.equity_curve[-1].trading_day - portfolio.equity_curve[0].trading_day
        ).days

        if elapsed_days <= 0:
            return None

        years = elapsed_days / self.CALENDAR_DAYS_PER_YEAR
        growth = float(portfolio.final_equity / portfolio.initial_capital)
        return Decimal(str((growth ** (1 / years) - 1) * 100))

    @staticmethod
    def _max_drawdown(
        portfolio: MultiPortfolioSimulationResult,
    ) -> Decimal:
        if not portfolio.equity_curve:
            return Decimal("0")

        peak = portfolio.equity_curve[0].equity
        maximum = Decimal("0")

        for point in portfolio.equity_curve:
            peak = max(peak, point.equity)

            if peak > 0:
                maximum = max(
                    maximum,
                    (peak - point.equity) / peak * Decimal("100"),
                )

        return maximum

    def _sharpe(
        self,
        portfolio: MultiPortfolioSimulationResult,
    ) -> Decimal | None:
        daily_returns = [
            float((current.equity - previous.equity) / previous.equity)
            for previous, current in zip(
                portfolio.equity_curve,
                portfolio.equity_curve[1:],
                strict=False,
            )
            if previous.equity != 0
        ]

        if len(daily_returns) < 2:
            return None

        volatility = stdev(daily_returns)

        if volatility == 0:
            return None

        return Decimal(str(mean(daily_returns) / volatility * sqrt(self.TRADING_DAYS_PER_YEAR)))

    @staticmethod
    def _exposure(
        portfolio: MultiPortfolioSimulationResult,
    ) -> Decimal:
        ratios = [
            point.invested_value / point.equity
            for point in portfolio.equity_curve
            if point.equity > 0
        ]

        if not ratios:
            return Decimal("0")

        return sum(ratios, Decimal("0")) / Decimal(len(ratios)) * Decimal("100")

    @staticmethod
    def _turnover(
        portfolio: MultiPortfolioSimulationResult,
    ) -> Decimal:
        traded_notional = sum(
            (
                trade.cost_basis + Decimal(trade.shares) * trade.exit_price + trade.exit_commission
                for trade in portfolio.trades
            ),
            Decimal("0"),
        )
        traded_notional += sum(
            (position.cost_basis for position in portfolio.open_positions),
            Decimal("0"),
        )

        if portfolio.initial_capital == 0:
            return Decimal("0")

        return traded_notional / portfolio.initial_capital * Decimal("100")

    @staticmethod
    def _average_positions(
        portfolio: MultiPortfolioSimulationResult,
    ) -> Decimal:
        if not portfolio.equity_curve:
            return Decimal("0")

        return Decimal(sum(point.open_positions for point in portfolio.equity_curve)) / Decimal(
            len(portfolio.equity_curve)
        )
