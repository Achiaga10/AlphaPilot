from __future__ import annotations

from decimal import Decimal

from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
    EquityCurvePoint,
    PortfolioConfig,
    PortfolioPosition,
    PortfolioSimulationResult,
    PortfolioTrade,
)
from alphapilot.strategy.signal import Signal


class PortfolioSimulator:
    """Simulates a long-only portfolio from historical signals."""

    BASIS_POINTS = Decimal("10000")

    def __init__(
        self,
        config: PortfolioConfig | None = None,
    ) -> None:
        self.config = config if config is not None else PortfolioConfig()

    def run(
        self,
        backtest: BacktestResult,
    ) -> PortfolioSimulationResult:
        cash = self.config.initial_capital

        position: PortfolioPosition | None = None

        trades: list[PortfolioTrade] = []

        equity_curve: list[EquityCurvePoint] = []

        bars = backtest.bars

        for index, current_bar in enumerate(bars):
            if index > 0:
                signal_bar = bars[index - 1]

                if signal_bar.signal == Signal.BUY and position is None:
                    (
                        cash,
                        position,
                    ) = self._open_position(
                        cash=cash,
                        signal_bar=signal_bar,
                        execution_bar=current_bar,
                    )

                elif signal_bar.signal == Signal.SELL and position is not None:
                    (
                        cash,
                        trade,
                    ) = self._close_position(
                        cash=cash,
                        position=position,
                        signal_bar=signal_bar,
                        execution_bar=current_bar,
                    )

                    trades.append(trade)

                    position = None

            shares = position.shares if position is not None else 0

            position_value = Decimal(shares) * current_bar.close

            equity = cash + position_value

            equity_curve.append(
                EquityCurvePoint(
                    trading_day=(current_bar.trading_day),
                    cash=cash,
                    shares=shares,
                    market_price=(current_bar.close),
                    equity=equity,
                )
            )

        final_equity = equity_curve[-1].equity if equity_curve else self.config.initial_capital

        return PortfolioSimulationResult(
            ticker=backtest.ticker,
            initial_capital=(self.config.initial_capital),
            final_equity=final_equity,
            equity_curve=tuple(equity_curve),
            trades=tuple(trades),
            open_position=position,
        )

    def _open_position(
        self,
        *,
        cash: Decimal,
        signal_bar: BacktestBarResult,
        execution_bar: BacktestBarResult,
    ) -> tuple[
        Decimal,
        PortfolioPosition | None,
    ]:
        execution_price = self._apply_buy_slippage(execution_bar.open)

        commission = self.config.commission_per_order

        if cash <= commission:
            return cash, None

        position_budget = cash * self.config.position_size_pct / Decimal("100")

        share_budget = min(
            position_budget,
            cash - commission,
        )

        shares = int(share_budget / execution_price)

        if shares <= 0:
            return cash, None

        total_cost = Decimal(shares) * execution_price + commission

        remaining_cash = cash - total_cost

        position = PortfolioPosition(
            entry_signal_day=(signal_bar.trading_day),
            entry_day=(execution_bar.trading_day),
            entry_price=execution_price,
            shares=shares,
            entry_commission=commission,
        )

        return (
            remaining_cash,
            position,
        )

    def _close_position(
        self,
        *,
        cash: Decimal,
        position: PortfolioPosition,
        signal_bar: BacktestBarResult,
        execution_bar: BacktestBarResult,
    ) -> tuple[
        Decimal,
        PortfolioTrade,
    ]:
        execution_price = self._apply_sell_slippage(execution_bar.open)

        commission = self.config.commission_per_order

        proceeds = Decimal(position.shares) * execution_price - commission

        updated_cash = cash + proceeds

        trade = PortfolioTrade(
            entry_signal_day=(position.entry_signal_day),
            entry_day=(position.entry_day),
            entry_price=(position.entry_price),
            exit_signal_day=(signal_bar.trading_day),
            exit_day=(execution_bar.trading_day),
            exit_price=execution_price,
            shares=position.shares,
            entry_commission=(position.entry_commission),
            exit_commission=commission,
        )

        return (
            updated_cash,
            trade,
        )

    def _apply_buy_slippage(
        self,
        price: Decimal,
    ) -> Decimal:
        slippage = self.config.slippage_bps / self.BASIS_POINTS

        return price * (Decimal("1") + slippage)

    def _apply_sell_slippage(
        self,
        price: Decimal,
    ) -> Decimal:
        slippage = self.config.slippage_bps / self.BASIS_POINTS

        return price * (Decimal("1") - slippage)
