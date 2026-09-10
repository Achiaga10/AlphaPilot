from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from alphapilot.backtesting.engine import BacktestingEngine
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.portfolio.risk import AverageTrueRangeCalculator
from alphapilot.strategy.achia_ema20 import AchiaStratEMA20Strategy
from alphapilot.strategy.evaluation import SignalReason
from alphapilot.strategy.indicators import calculate_ema_series
from alphapilot.strategy.profile import list_strategy_profiles
from alphapilot.strategy.signal import Signal


@pytest.mark.parametrize("close", ["90", "95", "99", "100", "101"])
def test_inclusive_continuous_entry_zone(close: str) -> None:
    result = AchiaStratEMA20Strategy.evaluate_indicators(
        close=Decimal(close), ema20=Decimal("100"), ema50=Decimal("89")
    )
    assert result.signal == Signal.BUY
    assert result.reason == SignalReason.ACHIA_EMA20_ENTRY_ZONE
    assert (result.position_exit_reason is not None) == (Decimal(close) < 100)


@pytest.mark.parametrize(
    ("close", "ema50"), [("89.99", "89"), ("101.01", "89"), ("100", "100"), ("100", "101")]
)
def test_entry_rejects_just_outside_zone_and_nonbullish_trend(close: str, ema50: str) -> None:
    assert (
        AchiaStratEMA20Strategy.evaluate_indicators(
            close=Decimal(close), ema20=Decimal("100"), ema50=Decimal(ema50)
        ).signal
        != Signal.BUY
    )


@pytest.mark.parametrize("close", ["99.99", "100", "100.01"])
def test_held_exit_is_strict_close_below_ema20_independent_of_trend(close: str) -> None:
    result = AchiaStratEMA20Strategy.evaluate_indicators(
        close=Decimal(close), ema20=Decimal("100"), ema50=Decimal("120")
    )
    assert (result.position_exit_reason == SignalReason.CLOSE_BELOW_EMA20) == (Decimal(close) < 100)


def history() -> tuple[Company, list[DailyCandle]]:
    company = Company(id=uuid4(), ticker="TEST", name="Controlled", is_active=True)
    candles = [
        DailyCandle(
            company_id=company.id,
            trading_day=date(2024, 1, 1) + timedelta(days=index),
            open=Decimal(100 + index),
            high=Decimal(102 + index),
            low=Decimal(98 + index),
            close=Decimal(100 + index),
            volume=1000,
        )
        for index in range(70)
    ]
    return company, candles


def test_insufficient_and_missing_ohlc_are_typed_unavailable() -> None:
    company, candles = history()
    strategy = AchiaStratEMA20Strategy()
    assert strategy.evaluate(company, []).reason == SignalReason.INSUFFICIENT_DATA
    assert strategy.evaluate(company, candles[:49]).reason == SignalReason.INSUFFICIENT_DATA
    candles[-1].low = None  # type: ignore[assignment]
    assert strategy.evaluate(company, candles).reason == SignalReason.INVALID_CANDLE_DATA


def test_existing_sma_seed_ema_and_simple_mean_atr_are_used() -> None:
    company, candles = history()
    result = AchiaStratEMA20Strategy().evaluate(company, candles)
    closes = [candle.close for candle in candles]
    assert result.ema20 == calculate_ema_series(closes, 20)[-1]
    assert result.ema50 == calculate_ema_series(closes, 50)[-1]
    assert AverageTrueRangeCalculator().calculate(candles, signal_day=candles[-1].trading_day) == 4


def test_future_candles_cannot_change_signal_ema_or_atr() -> None:
    company, candles = history()
    signal_day = candles[59].trading_day
    strategy = AchiaStratEMA20Strategy()
    before = strategy.evaluate_as_of(candles, signal_day=signal_day)
    atr = AverageTrueRangeCalculator()
    before_atr = atr.calculate(candles, signal_day=signal_day)
    for candle in candles[60:]:
        candle.open = candle.high = candle.low = candle.close = Decimal("99999")
    assert strategy.evaluate_as_of(candles, signal_day=signal_day) == before
    assert atr.calculate(candles, signal_day=signal_day) == before_atr
    replay = BacktestingEngine(strategy).run(
        company, candles, benchmark_ticker="SPY", benchmark_candles=[], end=signal_day
    )
    assert replay.bars[-1].evaluation == before
    assert replay.end == signal_day


def test_incomplete_current_session_is_excluded_at_1615_et_boundary() -> None:
    company, candles = history()
    today = candles[-1].trading_day
    policy = CompletedDailySessionPolicy(
        now_provider=lambda: datetime(today.year, today.month, today.day, 16, tzinfo=UTC)
    )
    strategy = AchiaStratEMA20Strategy(policy)
    assert strategy.evaluate(company, candles) == strategy.evaluate(company, candles[:-1])
    candles[-1].close = Decimal("1")
    assert strategy.evaluate(company, candles) == strategy.evaluate(company, candles[:-1])


def test_intraday_low_does_not_create_an_ema_strategy_exit() -> None:
    company, candles = history()
    baseline = AchiaStratEMA20Strategy().evaluate(company, candles)
    candles[-1].low = Decimal("1")
    changed = AchiaStratEMA20Strategy().evaluate(company, candles)
    assert changed == baseline
    assert changed.position_exit_reason is None


def test_achia_identity_is_separate_and_not_an_operational_profile() -> None:
    assert AchiaStratEMA20Strategy.STRATEGY_ID == "achia-strat-ema20-v1"
    assert AchiaStratEMA20Strategy.VERSION == 1
    assert [profile.profile_id for profile in list_strategy_profiles()] == [
        "ema20-pullback-v1",
        "micho-150-v1",
    ]
