from __future__ import annotations

from datetime import date
from decimal import Decimal

from alphapilot.backtesting.models import (
    EquityCurvePoint,
    PortfolioConfig,
    PortfolioPosition,
    PortfolioSimulationResult,
)
from alphapilot.database.models.daily_candle import DailyCandle


class BuyAndHoldSimulator:
    """Simulates buying once at the first open and holding to the end."""

    BASIS_POINTS = Decimal("10000")

    def run(
        self,
        *,
        ticker: str,
        candles: list[DailyCandle],
        start: date,
        end: date,
        config: PortfolioConfig | None = None,
    ) -> PortfolioSimulationResult:
        portfolio_config = config if config is not None else PortfolioConfig()

        ordered_candles = sorted(
            (candle for candle in candles if start <= candle.trading_day <= end),
            key=lambda candle: candle.trading_day,
        )

        if not ordered_candles:
            return PortfolioSimulationResult(
                ticker=ticker,
                initial_capital=(portfolio_config.initial_capital),
                final_equity=(portfolio_config.initial_capital),
                equity_curve=(),
                trades=(),
                open_position=None,
            )

        first_candle = ordered_candles[0]

        entry_price = self._apply_buy_slippage(
            first_candle.open,
            portfolio_config.slippage_bps,
        )

        commission = portfolio_config.commission_per_order

        available_cash = portfolio_config.initial_capital

        position_budget = available_cash * portfolio_config.position_size_pct / Decimal("100")

        share_budget = min(
            position_budget,
            available_cash - commission,
        )

        shares = int(share_budget / entry_price)

        if shares <= 0:
            equity_curve = tuple(
                EquityCurvePoint(
                    trading_day=candle.trading_day,
                    cash=available_cash,
                    shares=0,
                    market_price=candle.close,
                    equity=available_cash,
                )
                for candle in ordered_candles
            )

            return PortfolioSimulationResult(
                ticker=ticker,
                initial_capital=(portfolio_config.initial_capital),
                final_equity=available_cash,
                equity_curve=equity_curve,
                trades=(),
                open_position=None,
            )

        total_cost = Decimal(shares) * entry_price + commission

        cash = available_cash - total_cost

        position = PortfolioPosition(
            entry_signal_day=(first_candle.trading_day),
            entry_day=(first_candle.trading_day),
            entry_price=entry_price,
            shares=shares,
            entry_commission=commission,
        )

        equity_curve = tuple(
            EquityCurvePoint(
                trading_day=candle.trading_day,
                cash=cash,
                shares=shares,
                market_price=candle.close,
                equity=(cash + Decimal(shares) * candle.close),
            )
            for candle in ordered_candles
        )

        final_equity = equity_curve[-1].equity

        return PortfolioSimulationResult(
            ticker=ticker,
            initial_capital=(portfolio_config.initial_capital),
            final_equity=final_equity,
            equity_curve=equity_curve,
            trades=(),
            open_position=position,
        )

    def _apply_buy_slippage(
        self,
        price: Decimal,
        slippage_bps: Decimal,
    ) -> Decimal:
        slippage = slippage_bps / self.BASIS_POINTS

        return price * (Decimal("1") + slippage)
