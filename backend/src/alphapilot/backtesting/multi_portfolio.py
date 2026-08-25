from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from alphapilot.backtesting.candidate_selection import (
    CandidateSelectionPolicy,
    ExecutableCandidate,
    TickerAscendingSelectionPolicy,
)
from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioConfig,
    MultiPortfolioEquityPoint,
    MultiPortfolioPosition,
    MultiPortfolioSimulationResult,
    MultiPortfolioTrade,
)
from alphapilot.strategy.signal import Signal


class MultiPortfolioSimulator:
    """Executes multiple ticker backtests against one shared cash balance."""

    BASIS_POINTS = Decimal("10000")

    def __init__(
        self,
        config: MultiPortfolioConfig | None = None,
        selection_policy: CandidateSelectionPolicy | None = None,
    ) -> None:
        self.config = config if config is not None else MultiPortfolioConfig()
        self.selection_policy = (
            selection_policy if selection_policy is not None else TickerAscendingSelectionPolicy()
        )

    def run(
        self,
        backtests: dict[str, BacktestResult],
    ) -> MultiPortfolioSimulationResult:
        normalized = {ticker.upper(): result for ticker, result in backtests.items()}
        bars_by_ticker_day = {
            ticker: {bar.trading_day: bar for bar in result.bars}
            for ticker, result in normalized.items()
        }
        calendar = sorted(
            {bar.trading_day for result in normalized.values() for bar in result.bars}
        )
        executable_by_day: dict[date, list[ExecutableCandidate]] = defaultdict(list)

        for ticker, result in normalized.items():
            for signal_bar, execution_bar in zip(
                result.bars,
                result.bars[1:],
                strict=False,
            ):
                executable_by_day[execution_bar.trading_day].append(
                    ExecutableCandidate(
                        ticker=ticker,
                        signal_bar=signal_bar,
                        execution_bar=execution_bar,
                    )
                )

        cash = self.config.initial_capital
        positions: dict[str, MultiPortfolioPosition] = {}
        trades: list[MultiPortfolioTrade] = []
        latest_closes: dict[str, Decimal] = {}
        equity_curve: list[MultiPortfolioEquityPoint] = []

        for trading_day in calendar:
            candidates = executable_by_day[trading_day]

            exits = sorted(
                (
                    candidate
                    for candidate in candidates
                    if candidate.signal_bar.signal == Signal.SELL
                ),
                key=lambda candidate: candidate.ticker,
            )

            for candidate in exits:
                position = positions.get(candidate.ticker)

                if position is None:
                    continue

                cash, trade = self._close_position(
                    cash=cash,
                    position=position,
                    candidate=candidate,
                )
                trades.append(trade)
                del positions[candidate.ticker]

            buys = [
                candidate
                for candidate in candidates
                if candidate.signal_bar.signal == Signal.BUY and candidate.ticker not in positions
            ]

            for candidate in self.selection_policy.order(buys):
                if len(positions) >= self.config.max_positions:
                    break

                equity_at_open = cash + sum(
                    Decimal(position.shares)
                    * self._valuation_price_at_open(
                        ticker=ticker,
                        trading_day=trading_day,
                        bars_by_ticker_day=bars_by_ticker_day,
                        latest_closes=latest_closes,
                    )
                    for ticker, position in positions.items()
                )

                cash, position = self._open_position(
                    cash=cash,
                    equity=equity_at_open,
                    candidate=candidate,
                )

                if position is not None:
                    positions[candidate.ticker] = position

            for ticker, bars_by_day in bars_by_ticker_day.items():
                bar = bars_by_day.get(trading_day)

                if bar is not None:
                    latest_closes[ticker] = bar.close

            invested_value = sum(
                (
                    Decimal(position.shares) * latest_closes[ticker]
                    for ticker, position in positions.items()
                ),
                Decimal("0"),
            )
            equity = cash + invested_value

            if cash < 0:
                raise RuntimeError("multi-stock portfolio cash became negative")

            equity_curve.append(
                MultiPortfolioEquityPoint(
                    trading_day=trading_day,
                    cash=cash,
                    invested_value=invested_value,
                    equity=equity,
                    open_positions=len(positions),
                )
            )

        final_equity = equity_curve[-1].equity if equity_curve else self.config.initial_capital

        return MultiPortfolioSimulationResult(
            initial_capital=self.config.initial_capital,
            final_equity=final_equity,
            equity_curve=tuple(equity_curve),
            trades=tuple(trades),
            open_positions=tuple(positions[ticker] for ticker in sorted(positions)),
        )

    def _valuation_price_at_open(
        self,
        *,
        ticker: str,
        trading_day: date,
        bars_by_ticker_day: dict[str, dict[date, BacktestBarResult]],
        latest_closes: dict[str, Decimal],
    ) -> Decimal:
        bar = bars_by_ticker_day[ticker].get(trading_day)

        if bar is not None:
            return bar.open

        return latest_closes[ticker]

    def _open_position(
        self,
        *,
        cash: Decimal,
        equity: Decimal,
        candidate: ExecutableCandidate,
    ) -> tuple[Decimal, MultiPortfolioPosition | None]:
        commission = self.config.commission_per_order

        if cash <= commission:
            return cash, None

        execution_price = self._apply_buy_slippage(candidate.execution_bar.open)
        target_budget = equity / Decimal(self.config.max_positions)
        share_budget = min(target_budget, cash - commission)
        shares = int(share_budget / execution_price)

        if shares <= 0:
            return cash, None

        total_cost = Decimal(shares) * execution_price + commission
        remaining_cash = cash - total_cost

        if remaining_cash < 0:
            raise RuntimeError("entry would make portfolio cash negative")

        return remaining_cash, MultiPortfolioPosition(
            ticker=candidate.ticker,
            entry_signal_day=candidate.signal_bar.trading_day,
            entry_day=candidate.execution_bar.trading_day,
            entry_price=execution_price,
            shares=shares,
            entry_commission=commission,
            entry_reason=candidate.signal_bar.evaluation.reason,
        )

    def _close_position(
        self,
        *,
        cash: Decimal,
        position: MultiPortfolioPosition,
        candidate: ExecutableCandidate,
    ) -> tuple[Decimal, MultiPortfolioTrade]:
        execution_price = self._apply_sell_slippage(candidate.execution_bar.open)
        commission = self.config.commission_per_order
        proceeds = Decimal(position.shares) * execution_price - commission
        updated_cash = cash + proceeds

        if updated_cash < 0:
            raise RuntimeError("exit would make portfolio cash negative")

        return updated_cash, MultiPortfolioTrade(
            ticker=position.ticker,
            entry_signal_day=position.entry_signal_day,
            entry_day=position.entry_day,
            entry_price=position.entry_price,
            exit_signal_day=candidate.signal_bar.trading_day,
            exit_day=candidate.execution_bar.trading_day,
            exit_price=execution_price,
            shares=position.shares,
            entry_commission=position.entry_commission,
            exit_commission=commission,
            entry_reason=position.entry_reason,
            exit_reason=candidate.signal_bar.evaluation.reason,
        )

    def _apply_buy_slippage(self, price: Decimal) -> Decimal:
        return price * (Decimal("1") + self.config.slippage_bps / self.BASIS_POINTS)

    def _apply_sell_slippage(self, price: Decimal) -> Decimal:
        return price * (Decimal("1") - self.config.slippage_bps / self.BASIS_POINTS)
