from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from alphapilot.backtesting.achia_reporting import distribution, write_rows
from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.portfolio_attribution import PortfolioAttributionCalculator
from alphapilot.backtesting.shauli import ShauliRun
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.strategy.shauli import ShauliReason, ShauliState
from alphapilot.strategy_lab.reporting import write_json_artifact


def percentage(count: int, total: int) -> Decimal | None:
    return Decimal(count) / total * 100 if total else None


def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = [row["pnl"] for row in rows]
    returns = [row["return_pct"] for row in rows]
    losses = -sum((value for value in pnl if value < 0), Decimal(0))
    wins = sum((value for value in pnl if value > 0), Decimal(0))
    rs = [row["realized_r"] for row in rows]
    rdist = distribution(rs)
    rdist["p25"] = sorted(rs)[int(Decimal(".25") * (len(rs) - 1))] if rs else None
    return {
        "count": len(rows),
        "win_rate_pct": percentage(sum(v > 0 for v in pnl), len(rows)),
        "profit_factor": wins / losses if losses else None,
        "expectancy_pct": sum(returns, Decimal(0)) / len(rows) if rows else None,
        "expectancy_dollars": sum(pnl, Decimal(0)) / len(rows) if rows else None,
        "trade_pct": distribution(returns),
        "realized_r": rdist,
        "winner_r": distribution([r["realized_r"] for r in rows if r["pnl"] > 0]),
        "loser_r": distribution([r["realized_r"] for r in rows if r["pnl"] < 0]),
        "loser_pct": distribution([r["return_pct"] for r in rows if r["pnl"] < 0]),
        "holding_days": distribution([Decimal(r["holding_days"]) for r in rows]),
        "gap_through_count": sum(r["gap_through"] for r in rows),
    }


def report_run(
    directory: Path,
    run: ShauliRun,
    histories: dict[str, list[DailyCandle]],
    *,
    end: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    portfolio = run.portfolio
    entry_by_id = {row["setup_id"]: row for row in run.entries}
    exit_by_id = {row["setup_id"]: row for row in run.exits}
    completed: list[dict[str, Any]] = []
    recovery: list[dict[str, Any]] = []
    for trade in portfolio.trades:
        entry = entry_by_id[trade.trade_id]
        inside = [
            b for b in histories[trade.ticker] if trade.entry_day < b.trading_day < trade.exit_day
        ]
        row = {
            **asdict(trade),
            **entry,
            **exit_by_id[trade.trade_id],
            "pnl": trade.pnl,
            "return_pct": trade.return_pct,
            "realized_r": trade.pnl / (trade.shares * entry["risk_per_share"]),
            "mfe_pct": (max(b.high for b in inside) / trade.entry_price - 1) * 100
            if inside
            else None,
            "mae_pct": (min(b.low for b in inside) / trade.entry_price - 1) * 100
            if inside
            else None,
            "excursion_censored": True,
            "full_interior_sessions": len(inside),
        }
        completed.append(row)
        if row["exit_reason"] == ShauliReason.STRUCTURAL_STOP:
            future = [b for b in histories[trade.ticker] if trade.exit_day < b.trading_day <= end]
            for horizon in (5, 10, 20):
                observable = len(future) >= horizon
                subset = future[:horizon]
                recovery.append(
                    {
                        "setup_id": trade.trade_id,
                        "ticker": trade.ticker,
                        "horizon": horizon,
                        "observable": observable,
                        "future_close_return_pct": (subset[-1].close / trade.exit_price - 1) * 100
                        if observable
                        else None,
                        "reached_original_entry": any(b.high >= trade.entry_price for b in subset)
                        if observable
                        else None,
                        "reached_original_target": any(b.high >= entry["target"] for b in subset)
                        if observable
                        else None,
                    }
                )
    funnel = {
        state.value: sum(any(s == state for _, s in setup.transitions) for setup in run.setups)
        for state in ShauliState
    }
    ready = sum(s.plan is not None for s in run.setups)
    ambiguous = sum(
        r["reason"] == ShauliReason.AMBIGUOUS_ENTRY_TARGET_ORDER for r in run.order_audit
    )
    triggered = sum(r["entry_touched"] for r in run.order_audit)
    valid = sum(
        r["known_at"] < r["entry_day"]
        and r["target_confirmed_at"] < r["entry_day"]
        and 0 < r["stop"] < r["entry_fill"] < r["target"]
        and r["initial_rr"] >= 2
        and r["equilibrium_distance"] <= 0
        for r in run.entries
    )
    attr = PortfolioAttributionCalculator().calculate(portfolio)
    summary = {
        "metrics": asdict(MultiPortfolioPerformanceMetricsCalculator().calculate(portfolio)),
        "attribution": asdict(attr),
        "gross_return_pct": (attr.gross_realized_pnl + attr.gross_unrealized_pnl)
        / portfolio.initial_capital
        * 100,
        "funnel": funnel,
        "setup_count": len(run.setups),
        "entry_ready_setups": ready,
        "discount_pass": sum(
            s.poi_evidence is not None and s.poi_evidence.discount_pass for s in run.setups
        ),
        "valid_target": sum(
            s.poi_evidence is not None
            and s.poi_evidence.discount_pass
            and s.poi_evidence.target_swing is not None
            for s in run.setups
        ),
        "rr_ge_2_pass": ready,
        "would_be_entry_trigger_bars": triggered,
        "entries": len(run.entries),
        "open_trades": len(portfolio.open_positions),
        "terminal_rejections": dict(
            sorted(
                Counter(
                    s.terminal_reason.value
                    for s in run.setups
                    if s.terminal_reason is not None
                    and not any(state == ShauliState.IN_POSITION for _, state in s.transitions)
                ).items()
            )
        ),
        "pending_at_end": sum(
            s.terminal_reason is None and s.state != ShauliState.IN_POSITION for s in run.setups
        ),
        "ambiguous_entry_target_order_count": ambiguous,
        "ambiguous_entry_target_order_pct_of_entry_ready_setups": percentage(ambiguous, ready),
        "ambiguous_entry_target_order_pct_of_would_be_entry_trigger_bars": percentage(
            ambiguous, triggered
        ),
        "risk_pct": distribution([r["risk_pct"] for r in run.entries]),
        "risk_dollars": distribution([r["risk_dollars"] for r in run.entries]),
        "planned_portfolio_risk_pct": distribution(
            [r["planned_portfolio_risk_pct"] for r in run.entries]
        ),
        "risk_above_pct_counts": {
            str(cap): sum(r["risk_pct"] > cap for r in run.entries) for cap in (5, 10, 20)
        },
        "initial_rr": distribution([r["initial_rr"] for r in run.entries]),
        "valid_provenance_pct": percentage(valid, len(run.entries)),
        "trades": stats(completed),
        "exit_attribution": {
            reason.value: stats([r for r in completed if r["exit_reason"] == reason])
            for reason in (ShauliReason.STRUCTURAL_STOP, ShauliReason.OPPOSING_LIQUIDITY_TARGET)
        },
        "poi_attribution": {
            key: stats([r for r in completed if r["poi_type"] == key])
            for key in ("FVG_ONLY", "FVG_OB_OVERLAP")
        },
        "structure_attribution": {
            key: stats([r for r in completed if r["confirmation_label"] == key])
            for key in ("BULLISH_BOS", "BULLISH_CHOCH")
        },
        "entry_bar_stop_ambiguities": sum(
            r["entry_bar"] and r["same_bar_ambiguity"] for r in run.exits
        ),
        "held_stop_target_ambiguities": sum(
            not r["entry_bar"] and r["same_bar_ambiguity"] for r in run.exits
        ),
        "minimum_cash": run.minimum_cash,
        "average_cash": sum((p.cash for p in portfolio.equity_curve), Decimal(0))
        / len(portfolio.equity_curve)
        if portfolio.equity_curve
        else portfolio.initial_capital,
        "final_cash": portfolio.equity_curve[-1].cash
        if portfolio.equity_curve
        else portfolio.initial_capital,
        "maximum_simultaneous_positions": run.maximum_simultaneous_positions,
        "allocation_rejections": dict(
            Counter(
                str(r["reason"])
                for r in run.order_audit
                if r["reason"] in (ShauliReason.MAX_POSITIONS, ShauliReason.INSUFFICIENT_ALLOCATION)
            )
        ),
    }
    terminal = sum(s.terminal_reason is not None for s in run.setups)
    assert terminal + summary["pending_at_end"] + len(portfolio.open_positions) == len(run.setups)
    assert len(run.entries) == len(completed) + len(portfolio.open_positions)
    if abs(attr.reconciliation_residual) > Decimal("1e-8"):
        raise ValueError("Shauli accounting reconciliation failed")
    for name, rows in {
        "setups": [asdict(s) for s in run.setups],
        "entries": run.entries,
        "trades": completed,
        "order_audit": run.order_audit,
        "equity": [asdict(p) for p in portfolio.equity_curve],
        "open_positions": [asdict(p) for p in portfolio.open_positions],
        "attribution": [asdict(t) for t in attr.tickers],
        "stop_recovery": recovery,
    }.items():
        write_rows(directory / f"{name}.csv", rows)
    write_json_artifact(directory / "setups.json", run.setups)
    write_json_artifact(directory / "summary.json", summary)
    return summary, completed
