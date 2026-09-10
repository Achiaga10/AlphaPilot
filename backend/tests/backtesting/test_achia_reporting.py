import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from alphapilot.backtesting.achia_reporting import distribution, entry_bucket, recovery_rows
from alphapilot.backtesting.candidate_selection import RelativeStrength20SelectionPolicy
from alphapilot.backtesting.models import BacktestBarResult, BacktestResult
from alphapilot.backtesting.multi_portfolio_service import (
    MultiPortfolioBacktestService,
    PreparedMultiPortfolioData,
)
from alphapilot.cli.research_achia_ema20 import report_run
from alphapilot.strategy.achia_ema20 import AchiaStratEMA20Strategy
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal


@pytest.mark.parametrize(
    "value,label",
    [
        ("-10", "[-10,-7.5)"),
        ("-7.5", "[-7.5,-5)"),
        ("-5", "[-5,-2.5)"),
        ("-2.5", "[-2.5,0)"),
        ("0", "[0,1]"),
        ("1", "[0,1]"),
        ("2", "OUTSIDE_ACHIA_ZONE"),
    ],
)
def test_descriptive_buckets_are_inclusive_without_retuning(value: str, label: str) -> None:
    assert entry_bucket(Decimal(value)) == label


def test_percentiles_use_existing_floor_convention_and_separate_median() -> None:
    values = distribution([Decimal("1"), Decimal("5"), Decimal("2"), Decimal("10")])
    assert values["median"] == Decimal("3.5")
    assert values["p50"] == Decimal("2")
    assert values["p90"] == Decimal("5")
    assert distribution([])["p90"] is None


def test_post_stop_returns_are_diagnostic_only_and_incomplete_windows_are_censored() -> None:
    start = date(2024, 1, 1)
    bars = tuple(
        BacktestBarResult(
            start + timedelta(days=i),
            Decimal("95"),
            Decimal("95"),
            StrategyEvaluation(Signal.HOLD, SignalReason.ACHIA_EMA20_NO_ENTRY),
        )
        for i in range(11)
    )
    prepared = PreparedMultiPortfolioData(
        start,
        bars[-1].trading_day,
        {"AAA": BacktestResult("AAA", start, bars[-1].trading_day, bars)},
        {},
        [],
        {},
        {},
        {},
        ("AAA",),
        (),
    )
    trade = {
        "trade_id": "AAA:1",
        "ticker": "AAA",
        "exit_day": start,
        "entry_fill": Decimal("100"),
        "exit_price": Decimal("90"),
        "exit_family": "PROTECTIVE_STOP",
    }
    row = recovery_rows([trade], prepared)[0]
    assert row["return_5_sessions_pct"] == (Decimal("95") / 90 - 1) * 100
    assert row["return_20_sessions_pct"] is None
    assert row["recovered_entry_within_20_sessions"] is None
    recovered = replace(bars[3], close=Decimal("101"))
    modified = replace(
        prepared,
        backtests={
            "AAA": replace(prepared.backtests["AAA"], bars=(*bars[:3], recovered, *bars[4:]))
        },
    )
    assert recovery_rows([trade], modified)[0]["recovered_entry_within_20_sessions"] is True


@pytest.mark.parametrize("achia", [True, False])
def test_full_report_serializes_reconciles_and_repeats_on_controlled_data(
    tmp_path: Path, achia: bool
) -> None:
    start = date(2024, 1, 2)
    bars = tuple(
        BacktestBarResult(
            trading_day=start + timedelta(days=i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("95") if i == 1 else Decimal("99"),
            close=Decimal("100"),
            evaluation=StrategyEvaluation(
                Signal.BUY if i != 1 else Signal.HOLD,
                SignalReason.ACHIA_EMA20_ENTRY_ZONE,
                ema20=Decimal("100"),
                ema50=Decimal("90"),
            ),
        )
        for i in range(4)
    )
    prepared = PreparedMultiPortfolioData(
        start,
        bars[-1].trading_day,
        {"AAA": BacktestResult("AAA", start, bars[-1].trading_day, bars)},
        {"AAA": []},
        [],
        {"AAA": "Technology"},
        {("AAA", row.trading_day): Decimal("0.2") for row in bars},
        {("AAA", row.trading_day): Decimal("3") for row in bars},
        ("AAA",),
        (),
    )
    # run_prepared must never call market-data adapters; no external/database inputs.
    adapter: Any = None
    service = MultiPortfolioBacktestService(
        adapter,
        adapter,
        adapter,
        AchiaStratEMA20Strategy(),
        stock_warmup_days=120,
        selection_policy=RelativeStrength20SelectionPolicy(),
    )
    freeze = {
        "protocol_fingerprint": "controlled",
        "configuration_fingerprint": "controlled",
        "source_sha256": {},
    }
    first, summary = report_run(
        tmp_path / "first", service=service, prepared=prepared, achia=achia, freeze=freeze
    )
    second, _ = report_run(
        tmp_path / "second", service=service, prepared=prepared, achia=achia, freeze=freeze
    )
    assert first == second
    assert first.attribution.reconciliation_residual == 0
    assert len(first.portfolio.open_positions) == 1
    assert len(first.portfolio.trades) == (1 if achia else 0)
    assert summary["diagnostics"]["native_boundary_coverage_pct"] == (100 if achia else 0)
    assert json.loads((tmp_path / "first/summary.json").read_text())["metadata"]["research_only"]
    for path in (tmp_path / "first").iterdir():
        assert path.read_bytes() == (tmp_path / "second" / path.name).read_bytes()
