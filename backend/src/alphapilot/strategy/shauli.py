"""Research-only Shauli DAILY V1. Not registered with the operational factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from alphapilot.database.models.daily_candle import DailyCandle


class ShauliState(StrEnum):
    IDLE = "IDLE"
    CONTEXT_IDENTIFIED = "CONTEXT_IDENTIFIED"
    LIQUIDITY_MAPPED = "LIQUIDITY_MAPPED"
    INDUCEMENT_IDENTIFIED = "INDUCEMENT_IDENTIFIED"
    LIQUIDITY_SWEPT = "LIQUIDITY_SWEPT"
    STRUCTURE_CONFIRMED = "STRUCTURE_CONFIRMED"
    DISPLACEMENT_CONFIRMED = "DISPLACEMENT_CONFIRMED"
    POI_READY = "POI_READY"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    ENTRY_READY = "ENTRY_READY"
    IN_POSITION = "IN_POSITION"
    TARGET_HIT = "TARGET_HIT"
    INVALIDATED = "INVALIDATED"


class ShauliReason(StrEnum):
    NO_VALID_STRUCTURE = "NO_VALID_STRUCTURE"
    NO_INDUCEMENT = "NO_INDUCEMENT"
    WAITING_FOR_LIQUIDITY_SWEEP = "WAITING_FOR_LIQUIDITY_SWEEP"
    SWEEP_NOT_CONFIRMED = "SWEEP_NOT_CONFIRMED"
    NO_STRUCTURE_SHIFT = "NO_STRUCTURE_SHIFT"
    NO_DISPLACEMENT = "NO_DISPLACEMENT"
    NO_VALID_FVG = "NO_VALID_FVG"
    NO_VALID_POI = "NO_VALID_POI"
    POI_NOT_IN_DISCOUNT = "POI_NOT_IN_DISCOUNT"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    INVALID_STOP_GEOMETRY = "INVALID_STOP_GEOMETRY"
    NO_LIQUIDITY_TARGET = "NO_LIQUIDITY_TARGET"
    INSUFFICIENT_ROOM_TO_TARGET = "INSUFFICIENT_ROOM_TO_TARGET"
    SETUP_READY = "SETUP_READY"
    LONG_READY = "LONG_READY"
    STRUCTURAL_STOP = "STRUCTURAL_STOP"
    OPPOSING_LIQUIDITY_TARGET = "OPPOSING_LIQUIDITY_TARGET"
    TARGET_CONSUMED = "TARGET_CONSUMED"
    AMBIGUOUS_ENTRY_TARGET_ORDER = "AMBIGUOUS_ENTRY_TARGET_ORDER"
    MAX_POSITIONS = "MAX_POSITIONS"
    INSUFFICIENT_ALLOCATION = "INSUFFICIENT_ALLOCATION"


@dataclass(frozen=True, slots=True)
class Swing:
    kind: str
    price: Decimal
    pivot_at: date
    confirmed_at: date


def confirmed_pivots(candles: list[DailyCandle]) -> tuple[Swing, ...]:
    """Only the pivot newly confirmable at this completed prefix's final bar."""
    if len(candles) < 5:
        return ()
    window = candles[-5:]
    pivot = window[2]
    others = window[:2] + window[3:]
    result = []
    if all(pivot.high > item.high for item in others):
        result.append(Swing("HIGH", pivot.high, pivot.trading_day, window[-1].trading_day))
    if all(pivot.low < item.low for item in others):
        result.append(Swing("LOW", pivot.low, pivot.trading_day, window[-1].trading_day))
    return tuple(result)


def structure(highs: list[Swing], lows: list[Swing]) -> str:
    if len(highs) < 2 or len(lows) < 2:
        return "UNAVAILABLE"
    if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
        return "BULLISH"
    if highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
        return "BEARISH"
    return "MIXED"


def close_break(bar: DailyCandle, swing: Swing) -> bool:
    return swing.kind == "HIGH" and swing.confirmed_at < bar.trading_day and bar.close > swing.price


def is_sweep(bar: DailyCandle, inducement: Swing) -> bool:
    return inducement.confirmed_at < bar.trading_day and bar.low < inducement.price < bar.close


@dataclass(frozen=True, slots=True)
class Zone:
    low: Decimal
    high: Decimal

    @property
    def midpoint(self) -> Decimal:
        return (self.low + self.high) / 2


def bullish_fvg(candles: list[DailyCandle]) -> Zone | None:
    if len(candles) < 3 or candles[-1].low <= candles[-3].high:
        return None
    return Zone(candles[-3].high, candles[-1].low)


def order_block(candles: list[DailyCandle]) -> DailyCandle | None:
    return next((bar for bar in reversed(candles) if bar.close < bar.open), None)


def select_poi(fvg: Zone, ob: Zone | None) -> tuple[Zone, str]:
    if ob is not None:
        overlap = Zone(max(fvg.low, ob.low), min(fvg.high, ob.high))
        if overlap.low < overlap.high:
            return overlap, "FVG_OB_OVERLAP"
    return fvg, "FVG_ONLY"


def structural_stop(sweep_low: Decimal, ob: Zone | None) -> Decimal:
    return min(sweep_low, ob.low) if ob else sweep_low


def nearest_target(
    highs: list[Swing], consumed: set[date], fill: Decimal, as_of: date
) -> Swing | None:
    eligible = [
        s
        for s in highs
        if s.kind == "HIGH"
        and s.price > fill
        and s.confirmed_at <= as_of
        and s.pivot_at not in consumed
    ]
    return min(eligible, key=lambda s: (s.price, s.pivot_at)) if eligible else None


def confirmation_label(prior_structure: str) -> str:
    return "BULLISH_CHOCH" if prior_structure == "BEARISH" else "BULLISH_BOS"


def target_rr(entry_fill: Decimal, stop: Decimal, target: Decimal) -> Decimal | None:
    if not 0 < stop < entry_fill < target:
        return None
    return (target - entry_fill) / (entry_fill - stop)


@dataclass(frozen=True, slots=True)
class ShauliPlan:
    known_at: date
    fvg: Zone
    ob: Zone | None
    ob_day: date | None
    poi: Zone
    poi_type: str
    sweep_low: Decimal
    range_high: Decimal
    stop: Decimal
    target_swing: Swing
    displacement_days: tuple[date, ...]

    @property
    def entry(self) -> Decimal:
        return self.poi.midpoint

    @property
    def equilibrium(self) -> Decimal:
        return (self.sweep_low + self.range_high) / 2

    @property
    def target(self) -> Decimal:
        return self.target_swing.price


@dataclass(slots=True)
class ShauliSetup:
    setup_id: str
    ticker: str
    bos_day: date
    bos_swing: Swing
    initial_highs: tuple[Swing, ...]
    initial_lows: tuple[Swing, ...]
    state: ShauliState = ShauliState.CONTEXT_IDENTIFIED
    inducement: Swing | None = None
    sweep_day: date | None = None
    sweep_low: Decimal | None = None
    reclaim_close: Decimal | None = None
    confirmation_swing: Swing | None = None
    confirmation_day: date | None = None
    confirmation_label: str | None = None
    plan: ShauliPlan | None = None
    poi_evidence: ShauliPoiEvidence | None = None
    terminal_reason: ShauliReason | None = None
    terminal_day: date | None = None
    transitions: list[tuple[date, ShauliState]] = field(default_factory=list)

    def transition(self, day: date, state: ShauliState) -> None:
        self.state = state
        self.transitions.append((day, state))


@dataclass(frozen=True, slots=True)
class ShauliPoiEvidence:
    known_at: date
    displacement_days: tuple[date, ...]
    fvg: Zone
    ob: Zone | None
    ob_day: date | None
    poi: Zone
    poi_type: str
    range_high: Decimal
    equilibrium: Decimal
    discount_pass: bool
    stop: Decimal
    target_swing: Swing | None
    planned_entry_fill: Decimal
    initial_rr: Decimal | None


class ShauliStrategy:
    STRATEGY_ID = "shauli-strat-v1"
    VERSION = 1

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.candles: list[DailyCandle] = []
        self.highs: list[Swing] = []
        self.lows: list[Swing] = []
        self.consumed_highs: set[date] = set()
        self.broken_highs: set[date] = set()
        self.setups: list[ShauliSetup] = []
        self.active: ShauliSetup | None = None
        self.in_position = False

    def cancel(self, day: date, reason: ShauliReason) -> None:
        if self.active is not None:
            self.active.terminal_reason = reason
            self.active.terminal_day = day
            self.active.transition(day, ShauliState.INVALIDATED)
            self.active = None

    def entered(self, day: date) -> None:
        if self.active is None or self.active.plan is None:
            raise ValueError("entry requires a complete active plan")
        self.active.transition(day, ShauliState.ENTRY_READY)
        self.active.transition(day, ShauliState.IN_POSITION)
        self.in_position = True

    def exited(self, day: date, reason: ShauliReason) -> None:
        if self.active is None or not self.in_position:
            raise ValueError("exit requires an existing position")
        self.active.terminal_day = day
        self.active.terminal_reason = reason
        self.active.transition(
            day,
            ShauliState.TARGET_HIT
            if reason == ShauliReason.OPPOSING_LIQUIDITY_TARGET
            else ShauliState.INVALIDATED,
        )
        self.active = None
        self.in_position = False

    def on_close(self, bar: DailyCandle, *, warmup: bool = False) -> None:
        if self.candles and bar.trading_day <= self.candles[-1].trading_day:
            raise ValueError("Shauli requires unique increasing completed sessions")
        self.candles.append(bar)
        for swing in self.highs:
            if bar.high >= swing.price:
                self.consumed_highs.add(swing.pivot_at)
        for swing in confirmed_pivots(self.candles):
            (self.highs if swing.kind == "HIGH" else self.lows).append(swing)
        bias = structure(self.highs, self.lows)
        if warmup or self.in_position:
            return
        if self.active is not None and bias != "BULLISH":
            self.cancel(bar.trading_day, ShauliReason.NO_VALID_STRUCTURE)
            return
        if self.active is None:
            if bias != "BULLISH":
                return
            eligible = [s for s in self.highs if s.confirmed_at < bar.trading_day]
            if not eligible:
                return
            swing = eligible[-1]
            if swing.pivot_at in self.broken_highs or not close_break(bar, swing):
                return
            self.broken_highs.add(swing.pivot_at)
            setup = ShauliSetup(
                f"{self.ticker}:{bar.trading_day}:{len(self.setups) + 1}",
                self.ticker,
                bar.trading_day,
                swing,
                tuple(self.highs[-2:]),
                tuple(self.lows[-2:]),
            )
            setup.transition(bar.trading_day, ShauliState.CONTEXT_IDENTIFIED)
            self.setups.append(setup)
            self.active = setup
            return
        setup = self.active
        if setup.inducement is None:
            low = self.lows[-1]
            if low.pivot_at > setup.bos_day and low.price > self.lows[-2].price:
                after = [b for b in self.candles if b.trading_day > low.pivot_at]
                if all(b.low >= low.price for b in after):
                    setup.inducement = low
                    setup.transition(bar.trading_day, ShauliState.LIQUIDITY_MAPPED)
                    setup.transition(bar.trading_day, ShauliState.INDUCEMENT_IDENTIFIED)
            return
        if setup.sweep_day is None:
            # A newer qualifying HL replaces an older unswept inducement only
            # when already confirmed before this session, never retroactively.
            low = self.lows[-1]
            if (
                low.pivot_at > setup.inducement.pivot_at
                and low.pivot_at > setup.bos_day
                and low.confirmed_at < bar.trading_day
                and low.price > self.lows[-2].price
                and all(
                    b.low >= low.price for b in self.candles[:-1] if b.trading_day > low.pivot_at
                )
            ):
                setup.inducement = low
            if bar.low >= setup.inducement.price:
                return
            if not is_sweep(bar, setup.inducement):
                self.cancel(bar.trading_day, ShauliReason.SWEEP_NOT_CONFIRMED)
                return
            highs = [s for s in self.highs if s.confirmed_at < bar.trading_day]
            if not highs:
                self.cancel(bar.trading_day, ShauliReason.NO_STRUCTURE_SHIFT)
                return
            setup.sweep_day = bar.trading_day
            setup.sweep_low = bar.low
            setup.reclaim_close = bar.close
            setup.confirmation_swing = highs[-1]
            setup.confirmation_label = confirmation_label(bias)
            setup.transition(bar.trading_day, ShauliState.LIQUIDITY_SWEPT)
            return
        assert setup.sweep_low is not None and setup.confirmation_swing is not None
        if setup.plan is not None:
            # Unfilled orders only. The simulator has already handled this bar's
            # opening/entry events before completed-session invalidation.
            if bar.low <= setup.plan.stop:
                self.cancel(bar.trading_day, ShauliReason.STRUCTURAL_STOP)
            elif bar.high >= setup.plan.target:
                self.cancel(bar.trading_day, ShauliReason.TARGET_CONSUMED)
            return
        if bar.low <= setup.sweep_low:
            self.cancel(bar.trading_day, ShauliReason.STRUCTURAL_STOP)
            return
        if setup.confirmation_day is None and close_break(bar, setup.confirmation_swing):
            setup.confirmation_day = bar.trading_day
            setup.transition(bar.trading_day, ShauliState.STRUCTURE_CONFIRMED)
        sequence = self.candles[-3:]
        if (
            len(sequence) < 3
            or sequence[0].trading_day <= setup.sweep_day
            or sequence[1].close <= sequence[1].open
            or sequence[1].close <= setup.confirmation_swing.price
        ):
            return
        fvg = bullish_fvg(sequence)
        if fvg is None:
            return
        setup.transition(bar.trading_day, ShauliState.DISPLACEMENT_CONFIRMED)
        sweep_sequence = [b for b in self.candles if setup.sweep_day <= b.trading_day]
        ob_bar = order_block([b for b in sweep_sequence if b.trading_day < sequence[1].trading_day])
        ob = Zone(ob_bar.low, ob_bar.high) if ob_bar else None
        poi, poi_type = select_poi(fvg, ob)
        range_high = max(b.high for b in sweep_sequence)
        setup.transition(bar.trading_day, ShauliState.POI_READY)
        stop = structural_stop(setup.sweep_low, ob)
        fill = poi.midpoint * Decimal("1.0005")
        target = nearest_target(self.highs, self.consumed_highs, fill, bar.trading_day)
        equilibrium = (setup.sweep_low + range_high) / 2
        setup.poi_evidence = ShauliPoiEvidence(
            bar.trading_day,
            tuple(b.trading_day for b in sequence),
            fvg,
            ob,
            ob_bar.trading_day if ob_bar else None,
            poi,
            poi_type,
            range_high,
            equilibrium,
            poi.midpoint <= equilibrium,
            stop,
            target,
            fill,
            target_rr(fill, stop, target.price) if target else None,
        )
        if poi.midpoint > equilibrium:
            self.cancel(bar.trading_day, ShauliReason.POI_NOT_IN_DISCOUNT)
            return
        if not 0 < stop < fill:
            self.cancel(bar.trading_day, ShauliReason.INVALID_STOP_GEOMETRY)
        elif target is None:
            self.cancel(bar.trading_day, ShauliReason.NO_LIQUIDITY_TARGET)
        elif (target.price - fill) / (fill - stop) < 2:
            self.cancel(bar.trading_day, ShauliReason.INSUFFICIENT_ROOM_TO_TARGET)
        else:
            setup.plan = ShauliPlan(
                bar.trading_day,
                fvg,
                ob,
                ob_bar.trading_day if ob_bar else None,
                poi,
                poi_type,
                setup.sweep_low,
                range_high,
                stop,
                target,
                tuple(b.trading_day for b in sequence),
            )
            setup.transition(bar.trading_day, ShauliState.WAITING_FOR_RETRACE)
