from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioRunResult
from alphapilot.backtesting.sprint12_protocol import (
    Sprint12ExitConfiguration,
    Sprint12ResearchStage,
)
from alphapilot.strategy.name import StrategyName

SURVIVORSHIP_WARNING = (
    "SURVIVORSHIP BIAS: historical runs use the current active S&P 500 constituent list, "
    "not a point-in-time universe."
)


@dataclass(slots=True, frozen=True)
class Sprint12ReportMetadata:
    strategy: str
    entry_configuration: str
    selection_policy: str
    sizing_policy: str
    exit_control: str
    protective_stop: str
    trailing_stop: str
    profit_policy: str
    atr_period: int
    protective_atr_multiple: Decimal | None
    trailing_atr_multiple: Decimal | None
    loss_control_source: str | None
    loss_control_policy_version: str | None
    loss_control_trigger: str | None
    cost_scenario: str
    commission_per_order: Decimal
    slippage_bps_per_side: Decimal
    requested_start: date
    requested_end: date
    actual_start: date | None
    actual_end: date | None
    research_stage: str
    fold_label: str
    universe: str
    initial_capital: Decimal
    max_positions: int
    survivorship_warning: str
    completed_session_semantics: str
    execution_semantics: str
    final_position_handling: str
    data_mode: str
    dataset_snapshot_id: str | None
    dataset_sha256: str | None
    universe_sha256: str | None
    provenance_status: str
    snapshot_git_revision: str | None
    snapshot_git_dirty: bool | None
    run_git_revision: str | None
    run_git_dirty: bool | None


def build_metadata(
    *,
    result: MultiPortfolioRunResult,
    strategy: StrategyName,
    entry_configuration: str,
    config: MultiPortfolioConfig,
    exit_configuration: Sprint12ExitConfiguration,
    stage: Sprint12ResearchStage,
    fold_label: str,
    start: date,
    end: date,
) -> Sprint12ReportMetadata:
    curve = result.portfolio.equity_curve
    management = exit_configuration.trade_management
    research_data = result.research_data
    return Sprint12ReportMetadata(
        strategy=strategy.value,
        entry_configuration=entry_configuration,
        selection_policy=result.selection_policy_name,
        sizing_policy=config.sizing_policy.value,
        exit_control="existing frozen strategy exit remains active",
        protective_stop=management.protective_stop.value,
        trailing_stop=management.trailing_stop.value,
        profit_policy=management.profit_management.value,
        atr_period=management.atr_period,
        protective_atr_multiple=management.protective_stop.atr_multiple,
        trailing_atr_multiple=management.trailing_stop.atr_multiple,
        loss_control_source=management.protective_stop.loss_control_source,
        loss_control_policy_version=management.protective_stop.policy_version,
        loss_control_trigger=(
            "DAILY_LOW_OR_GAP_OPEN"
            if management.protective_stop.loss_control_source is not None
            else None
        ),
        cost_scenario="cost-low",
        commission_per_order=config.commission_per_order,
        slippage_bps_per_side=config.slippage_bps,
        requested_start=start,
        requested_end=end,
        actual_start=curve[0].trading_day if curve else None,
        actual_end=curve[-1].trading_day if curve else None,
        research_stage=stage.value,
        fold_label=fold_label,
        universe=(
            "frozen snapshot universe"
            if research_data and research_data.data_mode == "FROZEN_SNAPSHOT"
            else "current active S&P 500 constituents (^GSPC)"
        ),
        initial_capital=config.initial_capital,
        max_positions=config.max_positions,
        survivorship_warning=SURVIVORSHIP_WARNING,
        completed_session_semantics=(
            "historical completed daily candles only; ATR and trailing levels use data "
            "available before the trigger session"
        ),
        execution_semantics=(
            "strategy signal T executes next ticker open; pre-known stop gaps fill at open, "
            "intraday breaches at stop/target, stop first when daily OHLC path is ambiguous; "
            "5 bps sell slippage then applies"
        ),
        final_position_handling="mark to final close; do not force-liquidate",
        data_mode=(research_data.data_mode if research_data else "OPERATIONAL_CURRENT"),
        dataset_snapshot_id=(
            str(research_data.dataset_snapshot_id)
            if research_data and research_data.dataset_snapshot_id
            else None
        ),
        dataset_sha256=research_data.dataset_sha256 if research_data else None,
        universe_sha256=research_data.universe_sha256 if research_data else None,
        provenance_status=(
            research_data.provenance_status if research_data else "UNVERSIONED_CURRENT"
        ),
        snapshot_git_revision=(research_data.snapshot_git_revision if research_data else None),
        snapshot_git_dirty=(research_data.snapshot_git_dirty if research_data else None),
        run_git_revision=research_data.run_git_revision if research_data else None,
        run_git_dirty=research_data.run_git_dirty if research_data else None,
    )


def write_sprint12_report(
    output_dir: Path,
    base_name: str,
    *,
    result: MultiPortfolioRunResult,
    metadata: Sprint12ReportMetadata,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        name: output_dir / f"{base_name}_{name}.{extension}"
        for name, extension in (
            ("summary", "json"),
            ("equity", "csv"),
            ("trades", "csv"),
            ("open_positions", "csv"),
            ("selection_audit", "csv"),
            ("attribution", "csv"),
            ("sector_attribution", "csv"),
            ("stop_recovery", "csv"),
        )
    }
    summary = {
        "metadata": asdict(metadata),
        "ticker_counts": {
            "successful": len(result.successful_tickers),
            "failed": len(result.failed_tickers),
            "failed_tickers": result.failed_tickers,
        },
        "metrics": asdict(result.metrics),
        "ranking_diagnostics": asdict(result.portfolio.ranking_diagnostics),
        "risk_diagnostics": asdict(result.portfolio.risk_diagnostics),
        "trade_management_diagnostics": asdict(result.portfolio.trade_management_diagnostics),
        "trade_outcome_diagnostics": _trade_outcome_summary(result),
        "loss_control_risk_diagnostics": _loss_control_risk_summary(result),
        "attribution": {
            "gross_realized_pnl": result.attribution.gross_realized_pnl,
            "gross_unrealized_pnl": result.attribution.gross_unrealized_pnl,
            "transaction_friction": result.attribution.transaction_friction,
            "realized_pnl": result.attribution.realized_pnl,
            "unrealized_pnl": result.attribution.unrealized_pnl,
            "total_pnl": result.attribution.total_pnl,
            "reconciliation_residual": result.attribution.reconciliation_residual,
            "top_1_positive_pnl_share_pct": (result.attribution.top_1_positive_pnl_share_pct),
            "top_5_positive_pnl_share_pct": (result.attribution.top_5_positive_pnl_share_pct),
            "positive_pnl_hhi": result.attribution.positive_pnl_hhi,
        },
        "spy_metrics": asdict(result.spy_metrics),
        "recovery_summary": _recovery_summary(result),
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, default=_json_default),
        encoding="utf-8",
    )

    _write_csv(
        paths["equity"],
        (
            "trading_day",
            "cash",
            "invested_value",
            "equity",
            "open_positions",
            "modeled_portfolio_risk",
            "cash_reserve",
            "max_sector_weight_pct",
        ),
        (
            (
                item.trading_day,
                item.cash,
                item.invested_value,
                item.equity,
                item.open_positions,
                item.modeled_portfolio_risk,
                item.cash_reserve,
                item.max_sector_weight_pct,
            )
            for item in result.portfolio.equity_curve
        ),
    )
    _write_csv(
        paths["trades"],
        (
            "trade_id",
            "ticker",
            "sector",
            "entry_signal_day",
            "entry_day",
            "entry_reference_price",
            "entry_price",
            "exit_signal_day",
            "exit_day",
            "exit_reference_price",
            "exit_price",
            "shares",
            "pnl",
            "return_pct",
            "holding_days",
            "mfe_pct",
            "mae_pct",
            "peak_giveback_pct",
            "initial_atr14",
            "initial_stop",
            "loss_control_source",
            "loss_control_as_of",
            "loss_control_policy_version",
            "risk_per_share",
            "entry_to_boundary_risk_pct",
            "initial_position_value",
            "planned_risk_dollars",
            "planned_risk_pct_of_entry_equity",
            "profit_target",
            "exit_reason",
            "strategy_exit_reason",
            "gap_through_stop",
            "position_closed",
            "entry_commission",
            "exit_commission",
        ),
        (
            (
                trade.trade_id,
                trade.ticker,
                trade.sector,
                trade.entry_signal_day,
                trade.entry_day,
                trade.entry_reference_price,
                trade.entry_price,
                trade.exit_signal_day,
                trade.exit_day,
                trade.exit_reference_price,
                trade.exit_price,
                trade.shares,
                trade.pnl,
                trade.return_pct,
                trade.holding_days,
                trade.mfe_pct,
                trade.mae_pct,
                trade.peak_giveback_pct,
                trade.initial_atr,
                trade.initial_stop,
                trade.loss_control_source,
                trade.loss_control_as_of,
                trade.loss_control_policy_version,
                _risk_per_share(trade.entry_price, trade.initial_stop),
                _risk_pct(trade.entry_price, trade.initial_stop),
                Decimal(trade.initial_shares or trade.shares) * trade.entry_price,
                _planned_risk_dollars(
                    trade.entry_price,
                    trade.initial_stop,
                    trade.initial_shares or trade.shares,
                ),
                _portfolio_risk_pct(
                    entry_price=trade.entry_price,
                    boundary=trade.initial_stop,
                    shares=trade.initial_shares or trade.shares,
                    entry_equity=trade.entry_equity,
                ),
                trade.profit_target,
                trade.exit_reason,
                trade.strategy_exit_reason,
                trade.gap_through_stop,
                trade.position_closed,
                trade.entry_commission,
                trade.exit_commission,
            )
            for trade in result.portfolio.trades
        ),
    )
    _write_csv(
        paths["open_positions"],
        (
            "trade_id",
            "ticker",
            "sector",
            "entry_signal_day",
            "entry_day",
            "entry_price",
            "shares",
            "initial_atr14",
            "initial_stop",
            "loss_control_source",
            "loss_control_as_of",
            "loss_control_policy_version",
            "risk_per_share",
            "entry_to_boundary_risk_pct",
            "initial_position_value",
            "planned_risk_dollars",
            "planned_risk_pct_of_entry_equity",
            "effective_stop",
            "profit_target",
            "final_price",
            "unrealized_pnl",
            "exit_reason",
        ),
        (
            (
                position.trade_id,
                position.ticker,
                position.sector,
                position.entry_signal_day,
                position.entry_day,
                position.entry_price,
                position.shares,
                position.initial_atr,
                position.initial_stop,
                position.loss_control_source,
                position.loss_control_as_of,
                position.loss_control_policy_version,
                _risk_per_share(position.entry_price, position.initial_stop),
                _risk_pct(position.entry_price, position.initial_stop),
                Decimal(position.initial_shares or position.shares) * position.entry_price,
                _planned_risk_dollars(
                    position.entry_price,
                    position.initial_stop,
                    position.initial_shares or position.shares,
                ),
                _portfolio_risk_pct(
                    entry_price=position.entry_price,
                    boundary=position.initial_stop,
                    shares=position.initial_shares or position.shares,
                    entry_equity=position.entry_equity,
                ),
                position.effective_stop,
                position.profit_target,
                dict(result.portfolio.final_prices)[position.ticker],
                position.unrealized_pnl(dict(result.portfolio.final_prices)[position.ticker]),
                "FINAL_OPEN_POSITION",
            )
            for position in result.portfolio.open_positions
        ),
    )
    _write_csv(
        paths["selection_audit"],
        tuple(asdict(result.portfolio.selection_audit[0]).keys())
        if result.portfolio.selection_audit
        else ("execution_day", "ticker"),
        (tuple(asdict(item).values()) for item in result.portfolio.selection_audit),
    )
    _write_csv(
        paths["attribution"],
        tuple(asdict(result.attribution.tickers[0]).keys())
        if result.attribution.tickers
        else ("ticker", "total_pnl"),
        (tuple(asdict(item).values()) for item in result.attribution.tickers),
    )
    _write_csv(
        paths["sector_attribution"],
        tuple(asdict(result.attribution.sectors[0]).keys())
        if result.attribution.sectors
        else ("sector", "total_pnl"),
        (tuple(asdict(item).values()) for item in result.attribution.sectors),
    )
    _write_csv(
        paths["stop_recovery"],
        tuple(asdict(result.exit_recovery_diagnostics[0]).keys())
        if result.exit_recovery_diagnostics
        else ("ticker", "exit_day"),
        (tuple(asdict(item).values()) for item in result.exit_recovery_diagnostics),
    )
    return tuple(paths.values())


def _recovery_summary(result: MultiPortfolioRunResult) -> dict[str, Any]:
    items = result.exit_recovery_diagnostics
    measurable = [
        item for item in items if item.recovered_entry_price_within_20_sessions is not None
    ]
    return {
        "stopped_trades": len(items),
        "measurable_20_session_recoveries": len(measurable),
        "recovered_entry_price_within_20_sessions": sum(
            item.recovered_entry_price_within_20_sessions is True for item in measurable
        ),
        "recovery_rate_pct": (
            Decimal(
                sum(item.recovered_entry_price_within_20_sessions is True for item in measurable)
            )
            / Decimal(len(measurable))
            * Decimal("100")
            if measurable
            else None
        ),
        "later_strategy_exit_signal_count": sum(
            item.later_strategy_exit_signal_day is not None for item in items
        ),
        "average_return_5_sessions_pct": _average_optional(
            [item.return_5_sessions_pct for item in items]
        ),
        "average_return_10_sessions_pct": _average_optional(
            [item.return_10_sessions_pct for item in items]
        ),
        "average_return_20_sessions_pct": _average_optional(
            [item.return_20_sessions_pct for item in items]
        ),
        "hindsight_only": True,
    }


def _trade_outcome_summary(result: MultiPortfolioRunResult) -> dict[str, Decimal | int | None]:
    returns = [trade.return_pct for trade in result.portfolio.trades]
    winners = [value for value in returns if value > 0]
    losers = [value for value in returns if value < 0]
    gross_pnl = result.attribution.gross_realized_pnl + result.attribution.gross_unrealized_pnl
    return {
        "winning_trade_count": len(winners),
        "losing_trade_count": len(losers),
        "average_winner_pct": _average_optional(winners),
        "average_loser_pct": _average_optional(losers),
        "median_loser_pct": _percentile(losers, Decimal("0.50")),
        "worst_trade_pct": min(returns) if returns else None,
        "expectancy_average_trade_pct": _average_optional(returns),
        "gross_return_pct": (
            gross_pnl / result.portfolio.initial_capital * Decimal("100")
            if result.portfolio.initial_capital > 0
            else None
        ),
        "net_return_pct": result.portfolio.total_return_pct,
        "transaction_friction": result.attribution.transaction_friction,
    }


def _loss_control_risk_summary(result: MultiPortfolioRunResult) -> dict[str, Any]:
    entries: dict[str, tuple[Decimal, Decimal, int, Decimal | None]] = {}
    for trade in result.portfolio.trades:
        if trade.initial_stop is not None:
            entries.setdefault(
                trade.trade_id,
                (
                    trade.entry_price,
                    trade.initial_stop,
                    trade.initial_shares or trade.shares,
                    trade.entry_equity,
                ),
            )
    for position in result.portfolio.open_positions:
        if position.initial_stop is not None:
            entries.setdefault(
                position.trade_id,
                (
                    position.entry_price,
                    position.initial_stop,
                    position.initial_shares or position.shares,
                    position.entry_equity,
                ),
            )
    all_entries = {trade.trade_id for trade in result.portfolio.trades} | {
        position.trade_id for position in result.portfolio.open_positions
    }
    risks = [
        (entry - boundary) / entry * Decimal("100")
        for entry, boundary, _, _ in entries.values()
        if entry > 0
    ]
    planned_dollars = [
        Decimal(shares) * (entry - boundary) for entry, boundary, shares, _ in entries.values()
    ]
    portfolio_risks = [
        value
        for entry, boundary, shares, equity in entries.values()
        if (
            value := _portfolio_risk_pct(
                entry_price=entry,
                boundary=boundary,
                shares=shares,
                entry_equity=equity,
            )
        )
        is not None
    ]
    stops = result.portfolio.trade_management_diagnostics.stop_hit_count
    return {
        "portfolio_entries": len(all_entries),
        "entries_with_valid_numeric_boundary": len(entries),
        "boundary_coverage_pct": (
            Decimal(len(entries)) / Decimal(len(all_entries)) * Decimal("100")
            if all_entries
            else None
        ),
        "risk_distance_p50_pct": _percentile(risks, Decimal("0.50")),
        "risk_distance_p75_pct": _percentile(risks, Decimal("0.75")),
        "risk_distance_p90_pct": _percentile(risks, Decimal("0.90")),
        "risk_distance_max_pct": max(risks) if risks else None,
        "average_planned_risk_dollars": _average_optional(planned_dollars),
        "average_planned_risk_pct_of_entry_equity": _average_optional(portfolio_risks),
        "stop_trigger_count": stops,
        "stop_out_rate_pct": (
            Decimal(stops) / Decimal(len(entries)) * Decimal("100") if entries else None
        ),
        "percentile_method": "sorted floor(q * (n - 1))",
    }


def _risk_per_share(entry_price: Decimal, boundary: Decimal | None) -> Decimal | None:
    return entry_price - boundary if boundary is not None else None


def _risk_pct(entry_price: Decimal, boundary: Decimal | None) -> Decimal | None:
    risk = _risk_per_share(entry_price, boundary)
    return (
        risk / entry_price * Decimal("100")
        if entry_price > 0 and risk is not None and risk > 0
        else None
    )


def _planned_risk_dollars(
    entry_price: Decimal, boundary: Decimal | None, shares: int
) -> Decimal | None:
    risk = _risk_per_share(entry_price, boundary)
    return Decimal(shares) * risk if risk is not None else None


def _portfolio_risk_pct(
    *,
    entry_price: Decimal,
    boundary: Decimal | None,
    shares: int,
    entry_equity: Decimal | None,
) -> Decimal | None:
    if entry_equity is None or entry_equity <= 0:
        return None
    risk = _risk_per_share(entry_price, boundary)
    return Decimal(shares) * risk / entry_equity * Decimal("100") if risk is not None else None


def _percentile(values: list[Decimal], quantile: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(quantile * Decimal(len(ordered) - 1))
    return ordered[index]


def _average_optional(values: Sequence[Decimal | None]) -> Decimal | None:
    available = [value for value in values if value is not None]
    return sum(available, Decimal("0")) / Decimal(len(available)) if available else None


def _write_csv(path: Path, headers: tuple[str, ...], rows: Any) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)


def _json_default(value: object) -> str:
    if isinstance(value, (Decimal, date)):
        return str(value)
    raise TypeError(f"cannot JSON serialize {type(value).__name__}")
