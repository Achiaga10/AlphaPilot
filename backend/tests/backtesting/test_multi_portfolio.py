from datetime import date, timedelta
from decimal import Decimal

import pytest

from alphapilot.backtesting.candidate_selection import (
    CandidateRejectionReason,
    RelativeStrength20SelectionPolicy,
)
from alphapilot.backtesting.models import (
    BacktestBarResult,
    BacktestResult,
)
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.strategy.evaluation import SignalReason, StrategyEvaluation
from alphapilot.strategy.signal import Signal

START = date(2026, 1, 5)


def bar(
    offset: int,
    *,
    signal: Signal,
    open_price: str = "100",
    close: str = "100",
) -> BacktestBarResult:
    reason = {
        Signal.BUY: SignalReason.EMA20_PULLBACK_RECLAIM,
        Signal.SELL: SignalReason.TREND_BREAKDOWN,
        Signal.HOLD: SignalReason.NO_PULLBACK,
    }[signal]
    return BacktestBarResult(
        trading_day=START + timedelta(days=offset),
        open=Decimal(open_price),
        close=Decimal(close),
        evaluation=StrategyEvaluation(signal=signal, reason=reason),
    )


def backtest(ticker: str, *bars: BacktestBarResult) -> BacktestResult:
    return BacktestResult(
        ticker=ticker,
        start=bars[0].trading_day if bars else None,
        end=bars[-1].trading_day if bars else None,
        bars=bars,
    )


def test_two_stocks_share_cash_and_can_be_held_simultaneously() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=2)
    ).run(
        {
            "AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
            "BBB": backtest("BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        }
    )

    assert len(result.open_positions) == 2
    assert {position.ticker for position in result.open_positions} == {"AAA", "BBB"}
    assert [position.shares for position in result.open_positions] == [5, 5]
    assert result.equity_curve[-1].cash == Decimal("0")
    assert result.equity_curve[-1].cash >= 0
    assert result.equity_curve[-1].equity == Decimal("1000")


def test_max_positions_and_deterministic_ticker_priority_are_enforced() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1)
    ).run(
        {
            "BBB": backtest("BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
            "AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        }
    )

    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticker == "AAA"
    assert result.open_positions[0].shares == 10


def test_whole_share_position_sizing_and_cash_floor() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=3)
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.HOLD, open_price="120"),
            )
        }
    )

    assert result.open_positions[0].shares == 2
    assert result.equity_curve[-1].cash == Decimal("760")
    assert min(point.cash for point in result.equity_curve) >= 0


def test_commission_and_slippage_apply_to_entry_and_exit() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("1000"),
            max_positions=1,
            commission_per_order=Decimal("5"),
            slippage_bps=Decimal("100"),
        )
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL, open_price="100", close="100"),
                bar(2, signal=Signal.HOLD, open_price="110", close="110"),
            )
        }
    )

    trade = result.trades[0]
    assert trade.entry_price == Decimal("101.00")
    assert trade.exit_price == Decimal("108.90")
    assert trade.shares == 9
    assert trade.entry_commission == Decimal("5")
    assert trade.exit_commission == Decimal("5")


def test_entry_and_exit_use_next_available_open() -> None:
    result = MultiPortfolioSimulator().run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY, close="130"),
                bar(3, signal=Signal.SELL, open_price="120", close="90"),
                bar(7, signal=Signal.HOLD, open_price="80", close="85"),
            )
        }
    )

    trade = result.trades[0]
    assert trade.entry_signal_day == START
    assert trade.entry_day == START + timedelta(days=3)
    assert trade.entry_price == Decimal("120")
    assert trade.exit_signal_day == START + timedelta(days=3)
    assert trade.exit_day == START + timedelta(days=7)
    assert trade.exit_price == Decimal("80")


def test_exit_releases_cash_before_same_day_entry() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1)
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL),
                bar(2, signal=Signal.HOLD),
            ),
            "BBB": backtest(
                "BBB",
                bar(1, signal=Signal.BUY),
                bar(2, signal=Signal.HOLD),
            ),
        }
    )

    assert len(result.trades) == 1
    assert result.trades[0].ticker == "AAA"
    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticker == "BBB"
    assert result.open_positions[0].entry_day == START + timedelta(days=2)


def test_repeated_buy_and_flat_sell_are_ignored() -> None:
    result = MultiPortfolioSimulator().run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.BUY),
                bar(2, signal=Signal.HOLD),
            ),
            "BBB": backtest(
                "BBB",
                bar(0, signal=Signal.SELL),
                bar(1, signal=Signal.HOLD),
            ),
        }
    )

    assert len(result.open_positions) == 1
    assert result.open_positions[0].ticker == "AAA"
    assert result.open_positions[0].entry_signal_day == START
    assert result.trades == ()


def test_last_day_buy_and_sell_cannot_execute() -> None:
    no_entry = MultiPortfolioSimulator().run({"AAA": backtest("AAA", bar(0, signal=Signal.BUY))})
    open_at_end = MultiPortfolioSimulator(MultiPortfolioConfig(max_positions=1)).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL, close="125"),
            )
        }
    )

    assert no_entry.open_positions == ()
    assert no_entry.trades == ()
    assert len(open_at_end.open_positions) == 1
    assert open_at_end.trades == ()
    assert open_at_end.final_equity == Decimal("125000")


def test_daily_equity_includes_all_positions_and_marks_final_close() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=2)
    ).run(
        {
            "AAA": backtest(
                "AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD, close="110")
            ),
            "BBB": backtest(
                "BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD, close="120")
            ),
        }
    )

    final = result.equity_curve[-1]
    assert final.open_positions == 2
    assert final.invested_value == Decimal("1150")
    assert final.equity == Decimal("1150")
    assert result.final_equity == Decimal("1150")


def test_config_rejects_invalid_constraints() -> None:
    with pytest.raises(ValueError, match="max_positions"):
        MultiPortfolioConfig(max_positions=0)

    with pytest.raises(ValueError, match="initial_capital"):
        MultiPortfolioConfig(initial_capital=Decimal("0"))


def test_rs20_selection_preserves_score_and_rejection_attribution() -> None:
    simulator = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1),
        selection_policy=RelativeStrength20SelectionPolicy(),
    )
    inputs = {
        "AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        "BBB": backtest("BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
    }
    scores = {
        ("AAA", START): Decimal("-0.10"),
        ("BBB", START): Decimal("0.20"),
    }

    result = simulator.run(inputs, ranking_scores=scores)

    assert result.open_positions[0].ticker == "BBB"
    assert len(result.selection_audit) == 2
    assert result.selection_audit[0].ticker == "BBB"
    assert result.selection_audit[0].ranking_score == Decimal("0.20")
    assert result.selection_audit[0].candidate_rank == 1
    assert result.selection_audit[0].selected is True
    assert result.selection_audit[1].ticker == "AAA"
    assert result.selection_audit[1].selected is False
    assert result.selection_audit[1].rejection_reason == CandidateRejectionReason.SLOTS_FULL
    assert result.ranking_diagnostics.total_candidates_considered == 2
    assert result.ranking_diagnostics.selected_candidates == 1
    assert result.ranking_diagnostics.rejected_candidates == 1
    assert result.ranking_diagnostics.constrained_days == 1
    assert result.ranking_diagnostics.average_selected_score == Decimal("0.20")
    assert result.ranking_diagnostics.average_rejected_score == Decimal("-0.10")


def test_ranking_does_not_change_exit_before_entry_or_sell_processing() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1),
        selection_policy=RelativeStrength20SelectionPolicy(),
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.SELL),
                bar(2, signal=Signal.HOLD),
            ),
            "BBB": backtest(
                "BBB",
                bar(1, signal=Signal.BUY),
                bar(2, signal=Signal.HOLD),
            ),
        },
        ranking_scores={
            ("AAA", START): Decimal("0"),
            ("BBB", START + timedelta(days=1)): Decimal("1"),
        },
    )

    assert result.trades[0].ticker == "AAA"
    assert result.open_positions[0].ticker == "BBB"


def test_same_ranked_input_produces_identical_portfolio_and_audit() -> None:
    simulator = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1),
        selection_policy=RelativeStrength20SelectionPolicy(),
    )
    inputs = {
        "BBB": backtest("BBB", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        "AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
    }
    scores = {("AAA", START): Decimal("0.1"), ("BBB", START): Decimal("0.2")}

    first = simulator.run(inputs, ranking_scores=scores)
    second = simulator.run(inputs, ranking_scores=scores)

    assert first == second


def test_unscored_rs20_candidate_is_counted_without_fabricated_score() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("1000"), max_positions=1),
        selection_policy=RelativeStrength20SelectionPolicy(),
    ).run(
        {"AAA": backtest("AAA", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD))},
        ranking_scores={("AAA", START): None},
    )

    assert result.selection_audit[0].ranking_score is None
    assert result.ranking_diagnostics.missing_score_candidates == 1


def test_allocation_rejection_is_audited() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(initial_capital=Decimal("50"), max_positions=1),
        selection_policy=RelativeStrength20SelectionPolicy(),
    ).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.HOLD, open_price="100"),
            )
        },
        ranking_scores={("AAA", START): Decimal("0.1")},
    )

    assert result.open_positions == ()
    assert result.selection_audit[0].selected is False
    assert (
        result.selection_audit[0].rejection_reason
        == CandidateRejectionReason.INSUFFICIENT_ALLOCATION
    )
    assert result.ranking_diagnostics.rejected_insufficient_allocation == 1


def test_atr_risk_sizing_enforces_frozen_risk_cash_and_sector_constraints() -> None:
    config = MultiPortfolioConfig(
        initial_capital=Decimal("100000"),
        max_positions=10,
        sizing_policy=SizingPolicyName.ATR_RISK,
        risk_config=PortfolioRiskConfig(),
    )
    result = MultiPortfolioSimulator(config).run(
        {
            "AAA": backtest(
                "AAA",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.HOLD, open_price="100", close="110"),
            ),
            "BBB": backtest(
                "BBB",
                bar(0, signal=Signal.BUY),
                bar(1, signal=Signal.HOLD, open_price="100", close="110"),
            ),
        },
        atr_values={("AAA", START): Decimal("5"), ("BBB", START): Decimal("5")},
        ticker_sectors={"AAA": "Technology", "BBB": "Technology"},
    )

    assert [position.shares for position in result.open_positions] == [100, 100]
    assert all(position.stop_distance == Decimal("10") for position in result.open_positions)
    assert all(
        position.modeled_risk_dollars == Decimal("1000") for position in result.open_positions
    )
    assert result.equity_curve[-1].cash == Decimal("80000")
    assert result.equity_curve[-1].cash >= result.equity_curve[-1].cash_reserve
    assert result.equity_curve[-1].modeled_portfolio_risk == Decimal("2000")
    assert result.risk_diagnostics.buy_approved == 2


def test_volatility_normalized_backtest_uses_one_ranked_candidate_batch() -> None:
    result = MultiPortfolioSimulator(
        MultiPortfolioConfig(
            initial_capital=Decimal("100000"),
            max_positions=2,
            sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
            risk_config=PortfolioRiskConfig(max_positions=2),
        ),
        selection_policy=RelativeStrength20SelectionPolicy(),
    ).run(
        {
            "LOW": backtest("LOW", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
            "HIGH": backtest("HIGH", bar(0, signal=Signal.BUY), bar(1, signal=Signal.HOLD)),
        },
        ranking_scores={
            ("LOW", START): Decimal("0.2"),
            ("HIGH", START): Decimal("0.1"),
        },
        atr_values={
            ("LOW", START): Decimal("2"),
            ("HIGH", START): Decimal("4"),
        },
        ticker_sectors={"LOW": "A", "HIGH": "B"},
    )
    assert [item.ticker for item in result.selection_audit] == ["LOW", "HIGH"]
    weights = [
        item.normalized_sizing_weight
        for item in result.selection_audit
        if item.normalized_sizing_weight is not None
    ]
    assert sum(weights, Decimal("0")) == Decimal("1")
    assert weights[0] > weights[1]
    assert result.equity_curve[-1].cash >= result.equity_curve[-1].cash_reserve
    assert result.equity_curve[-1].cash >= 0
