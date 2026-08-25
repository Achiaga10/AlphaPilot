from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from alphapilot.backtesting.candidate_selection import (
    CandidateRejectionReason,
    CandidateSelectionPolicy,
    ExecutableCandidate,
    TickerAscendingSelectionPolicy,
)
from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio_models import (
    CandidateSelectionAudit,
    MultiPortfolioConfig,
    MultiPortfolioEquityPoint,
    MultiPortfolioPosition,
    MultiPortfolioSimulationResult,
    MultiPortfolioTrade,
    RankingDiagnostics,
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
        *,
        ranking_scores: dict[tuple[str, date], Decimal | None] | None = None,
        ticker_sectors: dict[str, str | None] | None = None,
    ) -> MultiPortfolioSimulationResult:
        frozen_scores = ranking_scores if ranking_scores is not None else {}
        sectors = ticker_sectors if ticker_sectors is not None else {}
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
                        ranking_score=frozen_scores.get((ticker, signal_bar.trading_day)),
                    )
                )

        cash = self.config.initial_capital
        positions: dict[str, MultiPortfolioPosition] = {}
        trades: list[MultiPortfolioTrade] = []
        latest_closes: dict[str, Decimal] = {}
        equity_curve: list[MultiPortfolioEquityPoint] = []
        selection_audit: list[CandidateSelectionAudit] = []
        constrained_days = 0

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

            available_slots_at_start = self.config.max_positions - len(positions)

            if len(buys) > available_slots_at_start:
                constrained_days += 1

            for candidate_rank, candidate in enumerate(
                self.selection_policy.order(buys),
                start=1,
            ):
                available_slots = self.config.max_positions - len(positions)

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

                if available_slots <= 0:
                    selection_audit.append(
                        self._audit_decision(
                            candidate=candidate,
                            candidate_rank=candidate_rank,
                            selected=False,
                            rejection_reason=CandidateRejectionReason.SLOTS_FULL,
                            available_slots=available_slots,
                            cash=cash,
                            equity=equity_at_open,
                        )
                    )
                    continue

                cash, position = self._open_position(
                    cash=cash,
                    equity=equity_at_open,
                    candidate=candidate,
                    sector=sectors.get(candidate.ticker),
                )

                if position is not None:
                    positions[candidate.ticker] = position
                    selection_audit.append(
                        self._audit_decision(
                            candidate=candidate,
                            candidate_rank=candidate_rank,
                            selected=True,
                            rejection_reason=None,
                            available_slots=available_slots,
                            cash=cash + position.cost_basis,
                            equity=equity_at_open,
                        )
                    )
                else:
                    selection_audit.append(
                        self._audit_decision(
                            candidate=candidate,
                            candidate_rank=candidate_rank,
                            selected=False,
                            rejection_reason=(CandidateRejectionReason.INSUFFICIENT_ALLOCATION),
                            available_slots=available_slots,
                            cash=cash,
                            equity=equity_at_open,
                        )
                    )

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
            final_prices=tuple((ticker, latest_closes[ticker]) for ticker in sorted(positions)),
            selection_audit=tuple(selection_audit),
            ranking_diagnostics=self._build_ranking_diagnostics(
                selection_audit,
                constrained_days=constrained_days,
            ),
        )

    def _audit_decision(
        self,
        *,
        candidate: ExecutableCandidate,
        candidate_rank: int,
        selected: bool,
        rejection_reason: CandidateRejectionReason | None,
        available_slots: int,
        cash: Decimal,
        equity: Decimal,
    ) -> CandidateSelectionAudit:
        return CandidateSelectionAudit(
            execution_day=candidate.execution_bar.trading_day,
            signal_day=candidate.signal_bar.trading_day,
            ticker=candidate.ticker,
            selection_policy=self.selection_policy.name,
            ranking_score=candidate.ranking_score,
            candidate_rank=candidate_rank,
            selected=selected,
            rejection_reason=rejection_reason,
            available_slots=available_slots,
            cash=cash,
            equity=equity,
        )

    def _build_ranking_diagnostics(
        self,
        audit: list[CandidateSelectionAudit],
        *,
        constrained_days: int,
    ) -> RankingDiagnostics:
        selected = [item for item in audit if item.selected]
        rejected = [item for item in audit if not item.selected]
        selected_scores = [
            item.ranking_score for item in selected if item.ranking_score is not None
        ]
        rejected_scores = [
            item.ranking_score for item in rejected if item.ranking_score is not None
        ]
        total = len(audit)

        return RankingDiagnostics(
            total_candidates_considered=total,
            selected_candidates=len(selected),
            rejected_candidates=len(rejected),
            selection_rate_pct=(
                Decimal(len(selected)) / Decimal(total) * Decimal("100") if total else Decimal("0")
            ),
            constrained_days=constrained_days,
            rejected_slots_full=sum(
                item.rejection_reason == CandidateRejectionReason.SLOTS_FULL for item in rejected
            ),
            rejected_insufficient_allocation=sum(
                item.rejection_reason == CandidateRejectionReason.INSUFFICIENT_ALLOCATION
                for item in rejected
            ),
            average_selected_score=self._average_score(selected_scores),
            average_rejected_score=self._average_score(rejected_scores),
            missing_score_candidates=(
                sum(item.ranking_score is None for item in audit)
                if self.selection_policy.uses_scores
                else 0
            ),
        )

    @staticmethod
    def _average_score(scores: list[Decimal]) -> Decimal | None:
        if not scores:
            return None

        return sum(scores, Decimal("0")) / Decimal(len(scores))

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
        sector: str | None,
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
            sector=sector,
            entry_signal_day=candidate.signal_bar.trading_day,
            entry_day=candidate.execution_bar.trading_day,
            entry_reference_price=candidate.execution_bar.open,
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
            sector=position.sector,
            entry_signal_day=position.entry_signal_day,
            entry_day=position.entry_day,
            entry_reference_price=position.entry_reference_price,
            entry_price=position.entry_price,
            exit_signal_day=candidate.signal_bar.trading_day,
            exit_day=candidate.execution_bar.trading_day,
            exit_reference_price=candidate.execution_bar.open,
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
