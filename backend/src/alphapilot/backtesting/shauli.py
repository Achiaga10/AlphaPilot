"""Isolated pending-limit research adapter; existing next-OPEN engine is unchanged."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from alphapilot.backtesting.cost_scenarios import CostScenarioName, get_cost_scenario
from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioEquityPoint,
    MultiPortfolioPosition,
    MultiPortfolioSimulationResult,
    MultiPortfolioTrade,
)
from alphapilot.backtesting.ranking_features import RelativeStrength20Calculator
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.shauli import ShauliPlan, ShauliReason, ShauliSetup, ShauliStrategy

ZERO = Decimal("0")
SLIPPAGE = get_cost_scenario(CostScenarioName.COST_LOW).slippage_bps / Decimal("10000")


@dataclass(frozen=True, slots=True)
class ShauliExecution:
    reason: ShauliReason
    raw_exit: Decimal | None = None
    gap_through: bool = False
    same_bar_ambiguity: bool = False


def pending_execution(plan: ShauliPlan, bar: DailyCandle) -> ShauliExecution | None:
    if bar.trading_day <= plan.known_at:
        return None
    if bar.open <= plan.stop:
        return ShauliExecution(ShauliReason.STRUCTURAL_STOP)
    if bar.open >= plan.target:
        return ShauliExecution(ShauliReason.TARGET_CONSUMED)
    if bar.low > plan.entry:
        return ShauliExecution(ShauliReason.TARGET_CONSUMED) if bar.high >= plan.target else None
    if bar.low <= plan.stop:
        return ShauliExecution(
            ShauliReason.LONG_READY,
            plan.stop,
            same_bar_ambiguity=True,
        )
    if bar.high >= plan.target and plan.entry < bar.open < plan.target:
        return ShauliExecution(ShauliReason.AMBIGUOUS_ENTRY_TARGET_ORDER, same_bar_ambiguity=True)
    return ShauliExecution(
        ShauliReason.LONG_READY,
        plan.target if bar.high >= plan.target else None,
    )


def held_execution(plan: ShauliPlan, bar: DailyCandle) -> ShauliExecution | None:
    if bar.open <= plan.stop:
        return ShauliExecution(ShauliReason.STRUCTURAL_STOP, bar.open, gap_through=True)
    if bar.open >= plan.target:
        return ShauliExecution(ShauliReason.OPPOSING_LIQUIDITY_TARGET, bar.open)
    if bar.low <= plan.stop:
        return ShauliExecution(
            ShauliReason.STRUCTURAL_STOP,
            plan.stop,
            same_bar_ambiguity=bar.high >= plan.target,
        )
    if bar.high >= plan.target:
        return ShauliExecution(ShauliReason.OPPOSING_LIQUIDITY_TARGET, plan.target)
    return None


@dataclass(slots=True)
class ShauliRun:
    portfolio: MultiPortfolioSimulationResult
    setups: list[ShauliSetup]
    entries: list[dict[str, Any]]
    exits: list[dict[str, Any]]
    order_audit: list[dict[str, Any]]
    maximum_simultaneous_positions: int = 0
    minimum_cash: Decimal = Decimal("100000")


class ShauliSimulator:
    def run(
        self,
        histories: dict[str, list[DailyCandle]],
        *,
        start: date,
        end: date,
        spy: list[DailyCandle],
        sectors: dict[str, str | None],
        max_positions: int = 10,
    ) -> ShauliRun:
        if max_positions < 1:
            raise ValueError("max_positions must be positive")
        detectors = {ticker: ShauliStrategy(ticker) for ticker in sorted(histories)}
        daily: dict[date, dict[str, DailyCandle]] = {}
        for ticker, history in histories.items():
            previous: date | None = None
            for history_bar in history:
                if previous is not None and history_bar.trading_day <= previous:
                    raise ValueError("histories must be strictly ordered, without duplicates")
                previous = history_bar.trading_day
                if history_bar.trading_day < start:
                    detectors[ticker].on_close(history_bar, warmup=True)
                elif history_bar.trading_day <= end:
                    daily.setdefault(history_bar.trading_day, {})[ticker] = history_bar
        # SPY supplies cash-only dates and comparable curve boundaries.
        for spy_bar in spy:
            if start <= spy_bar.trading_day <= end:
                daily.setdefault(spy_bar.trading_day, {})
        cash = Decimal("100000")
        positions: dict[str, MultiPortfolioPosition] = {}
        prices: dict[str, Decimal] = {}
        trades: list[MultiPortfolioTrade] = []
        curve: list[MultiPortfolioEquityPoint] = []
        entries: list[dict[str, Any]] = []
        exits: list[dict[str, Any]] = []
        audit: list[dict[str, Any]] = []
        peak_positions = 0
        minimum_cash = cash

        def close_position(ticker: str, day: date, action: ShauliExecution) -> None:
            nonlocal cash
            position = positions.pop(ticker)
            assert action.raw_exit is not None
            fill = action.raw_exit * (1 - SLIPPAGE)
            cash += position.shares * fill
            trades.append(
                MultiPortfolioTrade(
                    ticker=ticker,
                    sector=position.sector,
                    entry_signal_day=position.entry_signal_day,
                    entry_day=position.entry_day,
                    entry_reference_price=position.entry_reference_price,
                    entry_price=position.entry_price,
                    exit_signal_day=day,
                    exit_day=day,
                    exit_reference_price=action.raw_exit,
                    exit_price=fill,
                    shares=position.shares,
                    entry_commission=ZERO,
                    exit_commission=ZERO,
                    entry_reason=None,
                    exit_reason=None,
                    trade_id=position.trade_id,
                    initial_stop=position.initial_stop,
                    profit_target=position.profit_target,
                    gap_through_stop=action.gap_through,
                    holding_days=(day - position.entry_day).days,
                    initial_shares=position.shares,
                    entry_equity=position.entry_equity,
                    loss_control_source="SHAULI_STRUCTURAL_STOP",
                    loss_control_as_of=position.entry_signal_day,
                    loss_control_policy_version="shauli-strat-v1",
                )
            )
            exits.append(
                {
                    "setup_id": position.trade_id,
                    "exit_reason": action.reason,
                    "same_bar_ambiguity": action.same_bar_ambiguity,
                    "gap_through": action.gap_through,
                    "entry_bar": day == position.entry_day,
                }
            )
            detectors[ticker].exited(day, action.reason)

        for day, bars in sorted(daily.items()):
            held_at_open = set(positions)
            for ticker in sorted(held_at_open):
                bar = bars.get(ticker)
                setup = detectors[ticker].active
                assert setup is not None and setup.plan is not None
                if bar is not None and (
                    bar.open <= setup.plan.stop or bar.open >= setup.plan.target
                ):
                    action = held_execution(setup.plan, bar)
                    assert action is not None
                    close_position(ticker, day, action)
            open_equity = cash + sum(
                (
                    p.shares * (bars[t].open if t in bars else prices[t])
                    for t, p in positions.items()
                ),
                ZERO,
            )
            candidates = []
            for ticker, detector in detectors.items():
                setup = detector.active
                if (
                    ticker not in bars
                    or detector.in_position
                    or setup is None
                    or setup.plan is None
                    or setup.plan.known_at >= day
                ):
                    continue
                signal_day = detector.candles[-1].trading_day
                score = RelativeStrength20Calculator().calculate(
                    stock_candles=detector.candles,
                    benchmark_candles=spy,
                    signal_day=signal_day,
                )
                candidates.append((ticker, setup, score, signal_day))
            candidates.sort(key=lambda c: (c[2] is None, -(c[2] or ZERO), c[0]))
            remaining = cash
            slots = max_positions - len(positions)
            reservations: dict[str, int] = {}
            reservation_reasons: dict[str, ShauliReason] = {}
            for ticker, setup, _, _ in candidates:
                assert setup.plan is not None
                # Opening cancellations are knowable before reservations.
                bar = bars[ticker]
                if bar.open <= setup.plan.stop or bar.open >= setup.plan.target:
                    continue
                fill = setup.plan.entry * (1 + SLIPPAGE)
                shares = int(min(remaining, open_equity / max_positions) / fill) if slots > 0 else 0
                reservations[ticker] = shares
                if not shares:
                    reservation_reasons[ticker] = (
                        ShauliReason.MAX_POSITIONS
                        if slots == 0
                        else ShauliReason.INSUFFICIENT_ALLOCATION
                    )
                if shares:
                    slots -= 1
                    remaining -= shares * fill
            for rank, (ticker, setup, score, signal_day) in enumerate(candidates, 1):
                assert setup.plan is not None
                plan = setup.plan
                bar = bars[ticker]
                action = pending_execution(plan, bar)
                shares = reservations.get(ticker, 0)
                row: dict[str, Any] = {
                    "setup_id": setup.setup_id,
                    "ticker": ticker,
                    "day": day,
                    "signal_day": signal_day,
                    "rank": rank,
                    "score": score,
                    "reserved_shares": shares,
                    "entry_touched": bar.low <= plan.entry,
                    "entry_ready": True,
                    "selected": False,
                    "reason": ShauliReason.WAITING_FOR_RETRACE,
                }
                audit.append(row)
                if action is None:
                    continue
                if action.reason != ShauliReason.LONG_READY:
                    row["reason"] = action.reason
                    detectors[ticker].cancel(day, action.reason)
                    continue
                if shares == 0:
                    row["reason"] = reservation_reasons[ticker]
                    continue
                fill = plan.entry * (1 + SLIPPAGE)
                rr = (plan.target - fill) / (fill - plan.stop)
                if not (0 < plan.stop < fill < plan.target and rr >= 2):
                    raise ValueError("frozen entry geometry invariant failed")
                cash -= shares * fill
                detectors[ticker].entered(day)
                positions[ticker] = MultiPortfolioPosition(
                    ticker=ticker,
                    sector=sectors.get(ticker),
                    entry_signal_day=plan.known_at,
                    entry_day=day,
                    entry_reference_price=plan.entry,
                    entry_price=fill,
                    shares=shares,
                    entry_commission=ZERO,
                    entry_reason=None,
                    stop_distance=fill - plan.stop,
                    modeled_risk_dollars=shares * (fill - plan.stop),
                    initial_shares=shares,
                    initial_stop=plan.stop,
                    effective_stop=plan.stop,
                    profit_target=plan.target,
                    trade_id=setup.setup_id,
                    entry_equity=open_equity,
                    loss_control_source="SHAULI_STRUCTURAL_STOP",
                    loss_control_as_of=plan.known_at,
                    loss_control_policy_version="shauli-strat-v1",
                )
                entries.append(
                    {
                        "setup_id": setup.setup_id,
                        "ticker": ticker,
                        "entry_day": day,
                        "raw_entry": plan.entry,
                        "entry_fill": fill,
                        "shares": shares,
                        "stop": plan.stop,
                        "target": plan.target,
                        "risk_per_share": fill - plan.stop,
                        "risk_pct": (fill - plan.stop) / fill * 100,
                        "initial_rr": rr,
                        "risk_dollars": shares * (fill - plan.stop),
                        "entry_equity": open_equity,
                        "planned_portfolio_risk_pct": shares
                        * (fill - plan.stop)
                        / open_equity
                        * 100,
                        "equilibrium_distance": plan.entry - plan.equilibrium,
                        "sweep_distance": plan.entry - plan.sweep_low,
                        "poi_width": plan.poi.high - plan.poi.low,
                        "known_at": plan.known_at,
                        "target_confirmed_at": plan.target_swing.confirmed_at,
                        "poi_type": plan.poi_type,
                        "confirmation_label": setup.confirmation_label,
                    }
                )
                row.update(selected=True, reason=ShauliReason.LONG_READY)
                if cash < 0 or len(positions) > max_positions:
                    raise ValueError("shared cash/position invariant failed")
                peak_positions = max(peak_positions, len(positions))
                minimum_cash = min(minimum_cash, cash)
                if action.raw_exit is not None:
                    reason = (
                        ShauliReason.STRUCTURAL_STOP
                        if action.raw_exit == plan.stop
                        else ShauliReason.OPPOSING_LIQUIDITY_TARGET
                    )
                    close_position(
                        ticker,
                        day,
                        ShauliExecution(
                            reason,
                            action.raw_exit,
                            same_bar_ambiguity=action.same_bar_ambiguity,
                        ),
                    )
            # Opening exits were already processed; only remaining old holdings.
            for ticker in sorted(held_at_open & positions.keys()):
                bar = bars.get(ticker)
                setup = detectors[ticker].active
                assert setup is not None and setup.plan is not None
                if bar is not None:
                    action = held_execution(setup.plan, bar)
                    if action:
                        close_position(ticker, day, action)
            for ticker, bar in sorted(bars.items()):
                prices[ticker] = bar.close
                detectors[ticker].on_close(bar)
            invested = sum((p.shares * prices[t] for t, p in positions.items()), ZERO)
            curve.append(
                MultiPortfolioEquityPoint(
                    day,
                    cash,
                    invested,
                    cash + invested,
                    len(positions),
                    modeled_portfolio_risk=sum(
                        (p.modeled_risk_dollars for p in positions.values()), ZERO
                    ),
                )
            )
        portfolio = MultiPortfolioSimulationResult(
            Decimal("100000"),
            curve[-1].equity if curve else Decimal("100000"),
            tuple(curve),
            tuple(trades),
            tuple(positions[t] for t in sorted(positions)),
            tuple(sorted(prices.items())),
        )
        return ShauliRun(
            portfolio,
            [s for d in detectors.values() for s in d.setups],
            entries,
            exits,
            audit,
            peak_positions,
            minimum_cash,
        )
