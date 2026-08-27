from __future__ import annotations

import csv
import json
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
        cost_scenario="cost-low",
        commission_per_order=config.commission_per_order,
        slippage_bps_per_side=config.slippage_bps,
        requested_start=start,
        requested_end=end,
        actual_start=curve[0].trading_day if curve else None,
        actual_end=curve[-1].trading_day if curve else None,
        research_stage=stage.value,
        fold_label=fold_label,
        universe="current active S&P 500 constituents (^GSPC)",
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


def _average_optional(values: list[Decimal | None]) -> Decimal | None:
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
