"""Synthetic definitions/causality/execution tests; never performance tuning."""

from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.backtesting.shauli import ShauliSimulator, held_execution, pending_execution
from alphapilot.backtesting.shauli_reporting import percentage, report_run
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.shauli import (
    ShauliPlan,
    ShauliSetup,
    ShauliStrategy,
    Swing,
    Zone,
    bullish_fvg,
    close_break,
    confirmation_label,
    confirmed_pivots,
    is_sweep,
    nearest_target,
    order_block,
    select_poi,
    structural_stop,
    structure,
    target_rr,
)
from alphapilot.strategy.shauli import (
    ShauliReason as R,
)
from alphapilot.strategy.shauli import (
    ShauliState as S,
)

BASE = date(2020, 1, 1)


def bar(index, o="105", h="109", low="99", c="104"):
    return DailyCandle(
        trading_day=BASE + timedelta(days=index),
        open=D(o),
        high=D(h),
        low=D(low),
        close=D(c),
        volume=1000,
    )


def swing(kind="HIGH", price="112", pivot=0, confirmed=2):
    return Swing(kind, D(price), BASE + timedelta(days=pivot), BASE + timedelta(days=confirmed))


def plan():
    return ShauliPlan(
        BASE + timedelta(days=5),
        Zone(D(99), D(101)),
        None,
        None,
        Zone(D(99), D(101)),
        "FVG_ONLY",
        D(95),
        D(110),
        D(95),
        swing(),
        (BASE + timedelta(days=3), BASE + timedelta(days=4), BASE + timedelta(days=5)),
    )


@pytest.mark.parametrize("kind", ["HIGH", "LOW"])
def test_strict_pivot_delayed_two_right_bars(kind):
    candles = (
        [bar(i, "10", h, "5", "10") for i, h in enumerate(("12", "13", "15", "14", "12"))]
        if kind == "HIGH"
        else [bar(i, "10", "15", low, "10") for i, low in enumerate(("8", "7", "5", "6", "8"))]
    )
    assert confirmed_pivots(candles[:3]) == ()
    assert confirmed_pivots(candles[:4]) == ()
    result = confirmed_pivots(candles)
    assert len(result) == 1
    assert result[0].kind == kind
    assert result[0].pivot_at == candles[2].trading_day
    assert result[0].confirmed_at == candles[4].trading_day


@pytest.mark.parametrize("equal_index", [0, 1, 3, 4])
def test_equal_high_rejects_pivot(equal_index):
    candles = [bar(i, "10", "15" if i in (2, equal_index) else "12", "5", "10") for i in range(5)]
    assert confirmed_pivots(candles) == ()


@pytest.mark.parametrize(
    "high,low,expected",
    [
        ("120", "100", "BULLISH"),
        ("100", "80", "BEARISH"),
        ("120", "80", "MIXED"),
        ("110", "90", "MIXED"),
    ],
)
def test_structure_exact_latest_pairs(high, low, expected):
    assert (
        structure([swing(price="110"), swing(price=high)], [swing("LOW", "90"), swing("LOW", low)])
        == expected
    )
    assert structure([], []) == "UNAVAILABLE"


@pytest.mark.parametrize(
    "index,close,expected",
    [(2, "113", False), (3, "112", False), (3, "113", True), (3, "111", False)],
)
def test_bos_is_prior_confirmed_close_not_wick(index, close, expected):
    assert close_break(bar(index, h="115", c=close), swing()) is expected


@pytest.mark.parametrize(
    "index,low,close,expected",
    [
        (2, "94", "96", False),
        (3, "94", "96", True),
        (3, "95", "96", False),
        (3, "94", "95", False),
        (3, "94", "94", False),
    ],
)
def test_sweep_requires_prior_confirmation_and_same_day_reclaim(index, low, close, expected):
    assert is_sweep(bar(index, low=low, c=close), swing("LOW", "95")) is expected


@pytest.mark.parametrize(
    "low,expected", [("101", Zone(D(100), D(101))), ("100", None), ("99", None)]
)
def test_fvg_exact_positive_width_and_third_bar(low, expected):
    candles = [bar(0, h="100"), bar(1), bar(2, low=low)]
    assert bullish_fvg(candles[:2]) is None
    assert bullish_fvg(candles) == expected


def test_ob_last_bearish_full_wicks_and_missing():
    candles = [
        bar(0, "100", "110", "90", "95"),
        bar(1, "100", "120", "80", "99"),
        bar(2, "100", "120", "99", "110"),
    ]
    assert order_block(candles) is candles[1]
    assert order_block(candles[2:]) is None
    assert select_poi(Zone(D(90), D(110)), Zone(D(95), D(120))) == (
        Zone(D(95), D(110)),
        "FVG_OB_OVERLAP",
    )
    assert select_poi(Zone(D(90), D(110)), Zone(D(110), D(120))) == (
        Zone(D(90), D(110)),
        "FVG_ONLY",
    )
    assert select_poi(Zone(D(90), D(110)), None)[1] == "FVG_ONLY"


@pytest.mark.parametrize(
    "ob,expected", [(None, "95"), (Zone(D(94), D(100)), "94"), (Zone(D(96), D(100)), "95")]
)
def test_structural_stop_no_buffer(ob, expected):
    assert structural_stop(D(95), ob) == D(expected)


@pytest.mark.parametrize(
    "entry,stop,target,expected",
    [
        ("100", "95", "110", "2"),
        ("100", "95", "109", "1.8"),
        ("100", "100", "110", None),
        ("100", "0", "110", None),
        ("100", "95", "100", None),
    ],
)
def test_rr_actual_fill_geometry(entry, stop, target, expected):
    assert target_rr(D(entry), D(stop), D(target)) == (D(expected) if expected else None)


def test_target_is_nearest_known_unconsumed_above_fill():
    highs = [
        swing(price="120"),
        swing(price="115", pivot=1, confirmed=3),
        swing(price="110", pivot=2, confirmed=9),
    ]
    assert nearest_target(highs, set(), D(100), BASE + timedelta(days=5)) == highs[1]
    assert nearest_target(highs, {highs[1].pivot_at}, D(100), BASE + timedelta(days=5)) == highs[0]
    assert nearest_target(highs, set(), D(121), BASE + timedelta(days=5)) is None


@pytest.mark.parametrize(
    "o,h,low,reason,exit_price,ambiguity",
    [
        ("94", "109", "90", R.STRUCTURAL_STOP, None, False),
        ("112", "115", "99", R.TARGET_CONSUMED, None, False),
        ("105", "110", "101", None, None, False),
        ("105", "113", "101", R.TARGET_CONSUMED, None, False),
        ("105", "109", "99", R.LONG_READY, None, False),
        ("105", "113", "99", R.AMBIGUOUS_ENTRY_TARGET_ORDER, None, True),
        ("105", "109", "94", R.LONG_READY, "95", True),
        ("105", "113", "94", R.LONG_READY, "95", True),
        ("100", "113", "99", R.LONG_READY, "112", False),
        ("99", "113", "98", R.LONG_READY, "112", False),
    ],
)
def test_pending_execution_exact_daily_order(o, h, low, reason, exit_price, ambiguity):
    result = pending_execution(plan(), bar(6, o, h, low))
    if reason is None:
        assert result is None
    else:
        assert result.reason == reason
        assert result.raw_exit == (D(exit_price) if exit_price else None)
        assert result.same_bar_ambiguity is ambiguity


def test_poi_creation_day_cannot_enter():
    assert pending_execution(plan(), bar(5)) is None
    assert pending_execution(plan(), bar(4)) is None
    assert plan().entry == 100
    assert plan().equilibrium == D("102.5")


@pytest.mark.parametrize(
    "o,h,low,reason,price,ambiguity",
    [
        ("90", "113", "89", R.STRUCTURAL_STOP, "90", False),
        ("113", "115", "94", R.OPPOSING_LIQUIDITY_TARGET, "113", False),
        ("105", "113", "94", R.STRUCTURAL_STOP, "95", True),
        ("105", "110", "95", R.STRUCTURAL_STOP, "95", False),
        ("105", "112", "99", R.OPPOSING_LIQUIDITY_TARGET, "112", False),
    ],
)
def test_held_open_precedence_and_stop_first(o, h, low, reason, price, ambiguity):
    action = held_execution(plan(), bar(7, o, h, low))
    assert action.reason == reason
    assert action.raw_exit == D(price)
    assert action.same_bar_ambiguity is ambiguity


def seeded_detector(monkeypatch):
    """Execution-only harness: supply an already valid plan, not a technical detector claim."""

    class Seeded(ShauliStrategy):
        def on_close(self, candle, *, warmup=False):
            self.candles.append(candle)
            if candle.trading_day == plan().known_at:
                setup = ShauliSetup(
                    f"{self.ticker}:seed", self.ticker, BASE, swing(), (), (), plan=plan()
                )
                setup.transition(candle.trading_day, S.WAITING_FOR_RETRACE)
                self.active = setup
                self.setups.append(setup)

    monkeypatch.setattr("alphapilot.backtesting.shauli.ShauliStrategy", Seeded)


def simulation(candles, tickers=("AAA",), max_positions=10):
    return ShauliSimulator().run(
        {t: candles for t in tickers},
        start=candles[0].trading_day,
        end=candles[-1].trading_day,
        spy=candles,
        sectors={},
        max_positions=max_positions,
    )


def test_approved_ambiguity_cancels_no_entry_no_trade_and_reporting(monkeypatch, tmp_path):
    seeded_detector(monkeypatch)
    candles = [bar(5), bar(6, h="113"), bar(7)]
    run = simulation(candles)
    assert run.entries == [] and run.portfolio.trades == () and run.portfolio.open_positions == ()
    assert run.setups[0].terminal_reason == R.AMBIGUOUS_ENTRY_TARGET_ORDER
    summary, _ = report_run(tmp_path, run, {"AAA": candles}, end=candles[-1].trading_day)
    assert summary["ambiguous_entry_target_order_count"] == 1
    assert summary["ambiguous_entry_target_order_pct_of_entry_ready_setups"] == 100
    assert summary["ambiguous_entry_target_order_pct_of_would_be_entry_trigger_bars"] == 100
    assert summary["metrics"]["final_equity"] == 100000
    assert percentage(0, 0) is None


def test_realized_cash_friction_reconciliation_and_no_recycle(monkeypatch):
    seeded_detector(monkeypatch)
    run = simulation([bar(5), bar(6, low="94"), bar(7, low="94")])
    assert len(run.entries) == len(run.portfolio.trades) == 1
    trade = run.portfolio.trades[0]
    assert trade.entry_price == D("100.05")
    assert trade.exit_price == D("94.9525")
    assert trade.shares == 99
    assert run.portfolio.final_equity == D(100000) + 99 * (D("94.9525") - D("100.05"))
    assert PortfolioAttributionCalculator().calculate(run.portfolio).reconciliation_residual == 0
    assert run.exits[0]["entry_bar"] and run.exits[0]["same_bar_ambiguity"]


def test_whole_shares_open_mtm_shared_capital_and_repeatable(monkeypatch):
    seeded_detector(monkeypatch)
    candles = [bar(5), bar(6), bar(7)]
    run = simulation(candles, tuple(f"T{i:02}" for i in range(12)))
    assert len(run.portfolio.open_positions) == 10
    assert all(p.cash >= 0 for p in run.portfolio.equity_curve)
    assert run.entries[0]["ticker"] == "T00"
    assert run.entries[-1]["ticker"] == "T09"
    assert PortfolioAttributionCalculator().calculate(run.portfolio).reconciliation_residual == 0
    repeated = simulation(candles, tuple(reversed([f"T{i:02}" for i in range(12)])))
    assert asdict(run) == asdict(repeated)


def test_future_close_and_spy_cannot_change_prior_order(monkeypatch):
    seeded_detector(monkeypatch)
    candles = [bar(i) for i in range(7)]
    run = simulation(candles)
    changed = candles[:-1] + [bar(6, c="108")]
    result = simulation(changed)
    assert run.entries == result.entries
    assert run.order_audit == result.order_audit
    extended = simulation(candles + [bar(7, "500", "600", "400", "500")])
    assert extended.entries == run.entries


def test_full_detector_prefixes_do_not_leak_future_swings():
    candles = [
        bar(i, str(100 + i % 7), str(110 + i % 7), str(90 + i % 7), str(101 + i % 7))
        for i in range(40)
    ]
    full = ShauliStrategy("AAA")
    for i, candle in enumerate(candles):
        full.on_close(candle)
        prefix = ShauliStrategy("AAA")
        for prior in candles[: i + 1]:
            prefix.on_close(prior)
        assert full.highs == prefix.highs and full.lows == prefix.lows
        assert [asdict(s) for s in full.setups] == [asdict(s) for s in prefix.setups]
        assert all(s.confirmed_at <= candle.trading_day for s in full.highs + full.lows)
    with pytest.raises(ValueError):
        full.on_close(candles[-1])


def test_structure_invalidation_cannot_be_relaxed_after_sweep():
    detector = ShauliStrategy("AAA")
    detector.highs = [swing(price="110"), swing(price="120")]
    detector.lows = [swing("LOW", "95"), swing("LOW", "94")]
    setup = ShauliSetup("AAA:1", "AAA", BASE, swing(), (), (), sweep_day=BASE, sweep_low=D(90))
    setup.transition(BASE, S.LIQUIDITY_SWEPT)
    detector.active = setup
    detector.setups.append(setup)
    detector.on_close(bar(10))
    assert setup.terminal_reason == R.NO_VALID_STRUCTURE
    assert detector.active is None
    assert confirmation_label("BEARISH") == "BULLISH_CHOCH"
    assert confirmation_label("BULLISH") == "BULLISH_BOS"


def test_stage_helpers_require_real_position():
    detector = ShauliStrategy("AAA")
    with pytest.raises(ValueError):
        detector.entered(BASE)
    with pytest.raises(ValueError):
        detector.exited(BASE, R.STRUCTURAL_STOP)


def displacement_component(high="130", target="140", bullish=True):
    """Component test starts at an explicitly supplied swept state, not a full setup claim."""
    detector = ShauliStrategy("AAA")
    detector.highs = [
        swing(price=target, pivot=-10, confirmed=-8),
        swing(price="105", pivot=-7, confirmed=-5),
        swing(price="108", pivot=-4, confirmed=-2),
    ]
    detector.lows = [swing("LOW", "85", -8, -6), swing("LOW", "95", -3, -1)]
    setup = ShauliSetup(
        "AAA:component",
        "AAA",
        BASE - timedelta(days=10),
        detector.highs[-1],
        (),
        (),
        inducement=detector.lows[-1],
        sweep_day=BASE,
        sweep_low=D(90),
        confirmation_swing=detector.highs[-1],
        confirmation_label="BULLISH_BOS",
    )
    setup.transition(BASE, S.LIQUIDITY_SWEPT)
    detector.active = setup
    detector.setups.append(setup)
    detector.on_close(bar(1, "98", "100", "95", "99"))
    detector.on_close(bar(2, "100" if bullish else "111", high, "99", "110"))
    assert setup.plan is None
    detector.on_close(bar(3, "105", "111", "102", "109"))
    return detector, setup


def test_displacement_close_break_fvg_completion_poi_and_discount():
    _, setup = displacement_component()
    assert setup.confirmation_day == BASE + timedelta(days=2)
    assert setup.plan is not None
    assert setup.plan.known_at == BASE + timedelta(days=3)
    assert setup.plan.fvg == Zone(D(100), D(102))
    assert setup.plan.poi == setup.plan.fvg
    assert setup.plan.entry == 101 and setup.plan.equilibrium == 110
    assert setup.plan.stop == 90 and setup.plan.ob is None
    assert [state for _, state in setup.transitions] == [
        S.LIQUIDITY_SWEPT,
        S.STRUCTURE_CONFIRMED,
        S.DISPLACEMENT_CONFIRMED,
        S.POI_READY,
        S.WAITING_FOR_RETRACE,
    ]
    assert pending_execution(setup.plan, bar(3)) is None


def test_bearish_middle_is_not_displacement():
    _, setup = displacement_component(bullish=False)
    assert setup.plan is None
    assert S.DISPLACEMENT_CONFIRMED not in [s for _, s in setup.transitions]


def test_rr_rejects_too_near_target_without_replacing_it():
    _, setup = displacement_component(target="120")
    # Displacement consumed this high, so it cannot be selected as future BSLQ.
    assert setup.plan is None and setup.terminal_reason == R.NO_LIQUIDITY_TARGET


def test_premium_poi_is_rejected():
    _, setup = displacement_component(high="111")
    assert setup.plan is None and setup.terminal_reason == R.POI_NOT_IN_DISCOUNT


def test_inducement_requires_post_bos_confirmed_higher_low():
    detector = ShauliStrategy("AAA")
    detector.highs = [swing(price="110"), swing(price="120")]
    detector.lows = [swing("LOW", "85"), swing("LOW", "95", 6, 8)]
    setup = ShauliSetup("AAA:inducement", "AAA", BASE + timedelta(days=5), swing(), (), ())
    detector.active = setup
    detector.setups.append(setup)
    detector.on_close(bar(9, low="96"))
    assert setup.inducement == detector.lows[-1]
    assert setup.state == S.INDUCEMENT_IDENTIFIED
    detector.on_close(bar(10, "100", "110", "94", "100"))
    assert setup.state == S.LIQUIDITY_SWEPT
    assert setup.sweep_day == BASE + timedelta(days=10)
    assert setup.reclaim_close == 100


def test_untriggered_higher_rank_order_keeps_reserved_slot(monkeypatch):
    seeded_detector(monkeypatch)
    aaa = [bar(5), bar(6, low="101")]
    bbb = [bar(5), bar(6, low="99")]
    run = ShauliSimulator().run(
        {"AAA": aaa, "BBB": bbb},
        start=aaa[0].trading_day,
        end=aaa[-1].trading_day,
        spy=aaa,
        sectors={},
        max_positions=1,
    )
    assert run.entries == []
    assert run.order_audit[0]["reserved_shares"] > 0
    assert run.order_audit[1]["reason"] == R.MAX_POSITIONS


def test_intraday_proceeds_not_reassigned_to_another_entry(monkeypatch):
    seeded_detector(monkeypatch)
    candles = [bar(5), bar(6, low="94")]
    run = simulation(candles, ("AAA", "BBB"), max_positions=1)
    assert len(run.entries) == 1 and run.entries[0]["ticker"] == "AAA"
    assert run.maximum_simultaneous_positions == 1
    assert run.order_audit[1]["reason"] == R.MAX_POSITIONS


def test_reporting_censors_entry_exit_and_recovery_after_period(monkeypatch, tmp_path):
    seeded_detector(monkeypatch)
    candles = [bar(5), bar(6), bar(7, low="94")]
    run = simulation(candles)
    future = candles + [bar(i, "500", "600", "400", "500") for i in range(8, 30)]
    summary, rows = report_run(tmp_path, run, {"AAA": future}, end=candles[-1].trading_day)
    assert rows[0]["mfe_pct"] is None and rows[0]["mae_pct"] is None
    assert rows[0]["excursion_censored"] is True
    assert summary["trades"]["count"] == 1
    content = (tmp_path / "stop_recovery.csv").read_text()
    assert "False" in content and "500" not in content
