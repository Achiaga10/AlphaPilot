from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from pathlib import Path
from statistics import median
from typing import Any

from alphapilot.backtesting.multi_portfolio_models import (
    MultiPortfolioPosition,
    MultiPortfolioSimulationResult,
    MultiPortfolioTrade,
)
from alphapilot.backtesting.multi_portfolio_service import PreparedMultiPortfolioData
from alphapilot.backtesting.trade_management import TradeManagementExitReason
from alphapilot.strategy.evaluation import SignalReason
from alphapilot.strategy.signal import Signal

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def distribution(values: list[Decimal]) -> dict[str, Any]:
    ordered = sorted(values)
    result: dict[str, Any] = {"count": len(values)}
    result["mean"] = sum(values, ZERO) / len(values) if values else None
    result["median"] = median(values) if values else None
    result["min"] = min(values) if values else None
    result["max"] = max(values) if values else None
    for label, quantile in (("p5", "0.05"), ("p50", "0.5"), ("p75", "0.75"), ("p90", "0.90")):
        result[label] = ordered[int(Decimal(quantile) * (len(values) - 1))] if values else None
    return result


def entry_bucket(distance_pct: Decimal) -> str:
    if distance_pct < -10 or distance_pct > 1:
        return "OUTSIDE_ACHIA_ZONE"
    for upper, label in (
        (Decimal("-7.5"), "[-10,-7.5)"),
        (Decimal("-5"), "[-7.5,-5)"),
        (Decimal("-2.5"), "[-5,-2.5)"),
        (ZERO, "[-2.5,0)"),
    ):
        if distance_pct < upper:
            return label
    return "[0,1]"


def risk_bucket(risk: Decimal | None) -> str:
    if risk is None:
        return "UNAVAILABLE"
    for upper, label in ((2, "(0,2]"), (4, "(2,4]"), (6, "(4,6]"), (10, "(6,10]")):
        if risk <= upper:
            return label
    return ">10"


def signal_rows(prepared: PreparedMultiPortfolioData) -> list[dict[str, Any]]:
    rows = []
    for ticker, backtest in sorted(prepared.backtests.items()):
        for index, bar in enumerate(backtest.bars):
            if bar.signal != Signal.BUY:
                continue
            ema20, ema50 = bar.evaluation.ema20, bar.evaluation.ema50
            distance = (bar.close / ema20 - 1) * HUNDRED if ema20 else None
            rows.append(
                {
                    "ticker": ticker,
                    "signal_day": bar.trading_day,
                    "next_session": backtest.bars[index + 1].trading_day
                    if index + 1 < len(backtest.bars)
                    else None,
                    "close": bar.close,
                    "ema20": ema20,
                    "ema50": ema50,
                    "atr14": prepared.atr_values.get((ticker, bar.trading_day)),
                    "entry_location_pct": distance,
                    "entry_bucket": entry_bucket(distance)
                    if distance is not None
                    else "UNAVAILABLE",
                    "ema_spread_pct": (ema20 - ema50) / ema50 * HUNDRED
                    if ema20 and ema50
                    else None,
                    "held_exit_also_true": bar.evaluation.position_exit_reason is not None,
                    "rs20_portfolio_only": prepared.ranking_scores.get((ticker, bar.trading_day)),
                }
            )
    return rows


def entry_row(item: MultiPortfolioTrade | MultiPortfolioPosition) -> dict[str, Any]:
    native = item.loss_control_policy_version == "achia-ema20-atr14-plus-1pct-stop-v1"
    risk = item.entry_price - item.initial_stop if item.initial_stop is not None else None
    return {
        "trade_id": item.trade_id,
        "ticker": item.ticker,
        "entry_signal_day": item.entry_signal_day,
        "entry_day": item.entry_day,
        "entry_reference_price": item.entry_reference_price,
        "entry_fill": item.entry_price,
        "signal_atr14": item.initial_atr,
        "loss_control_as_of": item.loss_control_as_of,
        "loss_control_policy_version": item.loss_control_policy_version,
        "one_percent_entry_component": item.entry_price * Decimal("0.01") if native else None,
        "stop_price": item.initial_stop,
        "total_stop_distance": risk,
        "risk_per_share": risk,
        "risk_pct": risk / item.entry_price * HUNDRED if risk is not None else None,
        "shares": item.shares,
        "position_value": item.entry_price * item.shares,
        "entry_equity": item.entry_equity,
        "planned_risk_dollars": risk * item.shares if risk is not None else None,
        "planned_portfolio_risk_pct": risk * item.shares / item.entry_equity * HUNDRED
        if risk is not None and item.entry_equity
        else None,
        "valid_native_boundary": bool(
            native
            and item.initial_atr is not None
            and item.initial_atr > 0
            and item.initial_stop is not None
            and 0 < item.initial_stop < item.entry_price
            and item.loss_control_as_of == item.entry_signal_day
            # Match the frozen execution expression's operation order. With
            # repeating ATR decimals, its algebraic rearrangement can differ
            # in the last Decimal place without changing the financial boundary.
            and item.initial_stop
            == item.entry_price - item.initial_atr - item.entry_price * Decimal("0.01")
        ),
    }


def entry_rows(portfolio: MultiPortfolioSimulationResult) -> list[dict[str, Any]]:
    return [entry_row(item) for item in portfolio.trades] + [
        entry_row(item) for item in portfolio.open_positions
    ]


def completed_rows(
    portfolio: MultiPortfolioSimulationResult,
    prepared: PreparedMultiPortfolioData,
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    facts = {(row["ticker"], row["signal_day"]): row for row in signals}
    rows = []
    for trade in portfolio.trades:
        signal = facts.get((trade.ticker, trade.entry_signal_day), {})
        row = {**entry_row(trade), **asdict(trade)}
        row.update(
            {
                "pnl": trade.pnl,
                "return_pct": trade.return_pct,
                "exit_family": "PROTECTIVE_STOP"
                if trade.exit_reason == TradeManagementExitReason.PROTECTIVE_STOP
                else "CLOSE_BELOW_EMA20"
                if trade.strategy_exit_reason == SignalReason.CLOSE_BELOW_EMA20
                else "EXISTING_STRATEGY_EXIT",
                "holding_sessions": sum(
                    trade.entry_day <= bar.trading_day <= trade.exit_day
                    for bar in prepared.backtests[trade.ticker].bars
                ),
                "entry_location_pct": signal.get("entry_location_pct"),
                "entry_bucket": signal.get("entry_bucket", "UNAVAILABLE"),
                "ema_spread_pct": signal.get("ema_spread_pct"),
                "stop_risk_bucket": risk_bucket(row["risk_pct"]),
                "exit_day_excursions_censored": trade.exit_reason
                == TradeManagementExitReason.PROTECTIVE_STOP
                and not trade.gap_through_stop,
            }
        )
        rows.append(row)
    return rows


def trade_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [row["return_pct"] for row in rows]
    winners = [value for value in returns if value > 0]
    losers = [value for value in returns if value < 0]
    gross_profit = sum((row["pnl"] for row in rows if row["pnl"] > 0), ZERO)
    gross_loss = -sum((row["pnl"] for row in rows if row["pnl"] < 0), ZERO)
    return {
        "completed_trades": len(rows),
        "returns_pct": distribution(returns),
        "expectancy_pct": distribution(returns)["mean"],
        "expectancy_dollars": distribution([row["pnl"] for row in rows])["mean"],
        "winners_pct": distribution(winners),
        "losers_pct": distribution(losers),
        "win_rate_pct": Decimal(len(winners)) / len(rows) * HUNDRED if rows else ZERO,
        "loss_rate_pct": Decimal(len(losers)) / len(rows) * HUNDRED if rows else ZERO,
        "profit_factor_dollars": gross_profit / gross_loss if gross_loss > 0 else None,
        "holding_calendar_days": distribution([Decimal(row["holding_days"]) for row in rows]),
        "holding_sessions": distribution([Decimal(row["holding_sessions"]) for row in rows]),
        "mfe_pct": distribution([row["mfe_pct"] for row in rows]),
        "mae_pct": distribution([row["mae_pct"] for row in rows]),
        "stop_rate_pct": Decimal(sum(row["exit_family"] == "PROTECTIVE_STOP" for row in rows))
        / len(rows)
        * HUNDRED
        if rows
        else ZERO,
        "exit_day_excursion_censored_count": sum(
            row["exit_day_excursions_censored"] for row in rows
        ),
    }


def recovery_rows(
    rows: list[dict[str, Any]], prepared: PreparedMultiPortfolioData
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if row["exit_family"] != "PROTECTIVE_STOP":
            continue
        future = [
            bar
            for bar in prepared.backtests[row["ticker"]].bars
            if bar.trading_day > row["exit_day"]
        ]
        recovered = any(bar.close >= row["entry_fill"] for bar in future[:20])
        record = {
            "trade_id": row["trade_id"],
            "ticker": row["ticker"],
            "exit_day": row["exit_day"],
            "future_sessions": min(len(future), 20),
            "recovered_entry_within_20_sessions": recovered
            if recovered or len(future) >= 20
            else None,
        }
        for horizon in (5, 10, 20):
            record[f"return_{horizon}_sessions_pct"] = (
                (future[horizon - 1].close / row["exit_price"] - 1) * HUNDRED
                if len(future) >= horizon
                else None
            )
        result.append(record)
    return result


def diagnostics(
    portfolio: MultiPortfolioSimulationResult,
    prepared: PreparedMultiPortfolioData,
    signals: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    entries = entry_rows(portfolio)
    if len(entries) != sum(item.selected for item in portfolio.selection_audit):
        raise ValueError("accepted-entry audit does not reconcile to completed/open positions")
    if len({row["trade_id"] for row in entries}) != len(entries):
        raise ValueError("duplicate managed entry or double exit")
    risk = [row["risk_pct"] for row in entries if row["risk_pct"] is not None]
    grouped = {
        "winners": [row for row in trades if row["return_pct"] > 0],
        "losers": [row for row in trades if row["return_pct"] < 0],
        **{
            family: [row for row in trades if row["exit_family"] == family]
            for family in sorted({row["exit_family"] for row in trades})
        },
    }
    by_location = {}
    for label in (
        "[-10,-7.5)",
        "[-7.5,-5)",
        "[-5,-2.5)",
        "[-2.5,0)",
        "[0,1]",
        "OUTSIDE_ACHIA_ZONE",
    ):
        by_location[label] = {
            "signals": sum(row["entry_bucket"] == label for row in signals),
            **trade_summary([row for row in trades if row["entry_bucket"] == label]),
        }
    recoveries = recovery_rows(trades, prepared)
    known_recovery = [
        row["recovered_entry_within_20_sessions"]
        for row in recoveries
        if row["recovered_entry_within_20_sessions"] is not None
    ]
    unavailable = Counter(
        bar.evaluation.reason.value
        for result in prepared.backtests.values()
        for bar in result.bars
        if bar.evaluation.reason
        in (SignalReason.INSUFFICIENT_DATA, SignalReason.INVALID_CANDLE_DATA)
    )
    return {
        "signals": {
            "technical_buys": len(signals),
            "no_next_session": sum(row["next_session"] is None for row in signals),
            "considered": len(portfolio.selection_audit),
            "accepted_entries": len(entries),
            "rejected_entries": sum(not item.selected for item in portfolio.selection_audit),
            "held_or_not_fresh": sum(row["next_session"] is not None for row in signals)
            - len(portfolio.selection_audit),
            "unavailable_evaluations": dict(unavailable),
        },
        "trade_outcomes": trade_summary(trades),
        "native_boundary_coverage_pct": Decimal(
            sum(row["valid_native_boundary"] for row in entries)
        )
        / len(entries)
        * HUNDRED
        if entries
        else ZERO,
        "stop_distance_pct": distribution(risk),
        "planned_risk_dollars": distribution(
            [
                row["planned_risk_dollars"]
                for row in entries
                if row["planned_risk_dollars"] is not None
            ]
        ),
        "planned_portfolio_risk_pct": distribution(
            [
                row["planned_portfolio_risk_pct"]
                for row in entries
                if row["planned_portfolio_risk_pct"] is not None
            ]
        ),
        "exit_and_outcome_groups": {
            label: trade_summary(group) for label, group in grouped.items()
        },
        "entry_location": by_location,
        "ema_spread_pct": distribution(
            [row["ema_spread_pct"] for row in trades if row["ema_spread_pct"] is not None]
        ),
        "stop_risk_groups": {
            label: trade_summary([row for row in trades if row["stop_risk_bucket"] == label])
            for label in ("(0,2]", "(2,4]", "(4,6]", "(6,10]", ">10", "UNAVAILABLE")
        },
        "post_stop_recovery": {
            "stops": len(recoveries),
            "known_20_session_recovery_outcomes": len(known_recovery),
            "censored": len(recoveries) - len(known_recovery),
            "recovery_rate_known_pct": Decimal(sum(known_recovery)) / len(known_recovery) * HUNDRED
            if known_recovery
            else None,
            **{
                f"return_{horizon}_sessions_pct": distribution(
                    [
                        row[f"return_{horizon}_sessions_pct"]
                        for row in recoveries
                        if row[f"return_{horizon}_sessions_pct"] is not None
                    ]
                )
                for horizon in (5, 10, 20)
            },
        },
    }


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["NO_ROWS"]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: value.value if isinstance(value, Enum) else value
                    for key, value in row.items()
                }
            )
