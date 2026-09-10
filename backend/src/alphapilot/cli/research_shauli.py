"""Run the one approved Shauli DAILY V1 study, with a read-only frozen dataset."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import selectors
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alphapilot.backtesting.achia_reporting import write_rows
from alphapilot.backtesting.benchmark import BuyAndHoldSimulator
from alphapilot.backtesting.candidate_selection import RelativeStrength20SelectionPolicy
from alphapilot.backtesting.models import PortfolioConfig
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioBacktestService
from alphapilot.backtesting.portfolio_metrics import PortfolioPerformanceMetricsCalculator
from alphapilot.backtesting.research_data_source import FrozenDatasetMarketDataSource
from alphapilot.backtesting.shauli import ShauliSimulator
from alphapilot.backtesting.shauli_reporting import report_run, stats
from alphapilot.core.config import settings
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.services.research_dataset import ResearchDatasetService, capture_git_revision
from alphapilot.strategy.micho150 import Micho150Strategy
from alphapilot.strategy_lab.identity import canonical_json, experiment_identity
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    DatasetBinding,
    ResearchPeriod,
    StrategyLabProtocol,
    StrategyLabResultSummary,
)
from alphapilot.strategy_lab.reporting import write_json_artifact
from alphapilot.strategy_lab.service import StrategyLabService
from alphapilot.strategy_lab.shauli_protocol import build_shauli_protocol, gate_checks, reject_stage

BACKEND = Path(__file__).resolve().parents[3]
DOCUMENT = BACKEND.parent / "docs/research/SHAULI_STRAT_PROTOCOL.md"


def source_hashes() -> dict[str, str]:
    paths = [
        p
        for directory in ("strategy", "backtesting", "strategy_lab", "research_data")
        for p in (BACKEND / "src/alphapilot" / directory).glob("*.py")
    ]
    paths += [Path(__file__), DOCUMENT]
    paths += [
        BACKEND / "src/alphapilot" / name
        for name in (
            "services/research_dataset.py",
            "repositories/research_dataset.py",
            "market/session.py",
            "database/models/daily_candle.py",
            "database/models/research_dataset.py",
        )
    ]
    return {
        p.relative_to(BACKEND.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }


def freeze_payload() -> dict[str, Any]:
    protocol = build_shauli_protocol()
    return {
        "protocol": json.loads(canonical_json(protocol)),
        "protocol_fingerprint": experiment_identity(protocol),
        "configuration_fingerprint": experiment_identity(protocol, protocol.candidates[0]),
        "source_sha256": source_hashes(),
    }


def summary_to_lab(summary: dict[str, Any]) -> StrategyLabResultSummary:
    m = summary["metrics"]
    a = summary["attribution"]
    return StrategyLabResultSummary(
        final_equity=m["final_equity"],
        total_return_pct=m["total_return_pct"],
        cagr_pct=m["cagr_pct"],
        max_drawdown_pct=m["max_drawdown_pct"],
        sharpe_ratio=m["sharpe_ratio"],
        calmar_ratio=m["calmar_ratio"],
        profit_factor=m["profit_factor"],
        win_rate_pct=m["win_rate_pct"],
        completed_trades=m["completed_trades"],
        exposure_pct=m["exposure_pct"],
        turnover_pct=m["turnover_pct"],
        realized_pnl=a["realized_pnl"],
        unrealized_pnl=a["unrealized_pnl"],
        top_5_positive_pnl_share_pct=a["top_5_positive_pnl_share_pct"],
    )


class ShauliResearchRunner:
    def __init__(self, output: Path, source: FrozenDatasetMarketDataSource) -> None:
        self.output = output
        self.source = source
        self.histories: dict[str, list[DailyCandle]] = {}
        self.sectors: dict[str, str | None] = {}
        self.spy: list[DailyCandle] = []
        self.preparation: dict[str, str] = {}
        self.results: dict[ResearchPeriod, dict[str, Any]] = {}

    async def prepare(self, period: ResearchPeriod) -> None:
        manifest = await self.source.manifest()
        benchmark = await self.source.get_company("SPY")
        if benchmark is None:
            raise ValueError("frozen SPY missing")
        self.spy = await self.source.get_history(benchmark.id, manifest.start, period.end)
        if not any(period.start <= b.trading_day <= period.end for b in self.spy):
            raise ValueError("no SPY sessions in period")
        self.histories = {}
        self.preparation = {}
        for member in await self.source.list_active("^GSPC"):
            company = await self.source.get_company(member.ticker)
            if company is None:
                raise ValueError("snapshot member lacks frozen company")
            bars = await self.source.get_history(company.id, manifest.start, period.end)
            if not any(b.trading_day >= period.start for b in bars):
                self.preparation[member.ticker] = "NO_FROZEN_HISTORY_IN_PERIOD"
                continue
            if any(
                not (0 < b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high)
                for b in bars
            ):
                raise ValueError(f"invalid frozen OHLC for {member.ticker}")
            self.histories[member.ticker] = bars
            self.sectors[member.ticker] = company.sector
        print(
            f"Prepared {len(self.histories)} tickers; "
            f"absent period history {len(self.preparation)}",
            flush=True,
        )

    def execute(self, period: ResearchPeriod) -> dict[str, Any]:
        if period in self.results:
            return self.results[period]
        directory = self.output / f"shauli_{period.start}_{period.end}"
        simulator = ShauliSimulator()
        independent_rows: list[dict[str, Any]] = []
        independent_tickers = []
        independent_summaries = []
        for ticker, bars in sorted(self.histories.items()):
            run = simulator.run(
                {ticker: bars},
                start=period.start,
                end=period.end,
                spy=self.spy,
                sectors=self.sectors,
                max_positions=1,
            )
            summary, rows = report_run(
                directory / "independent" / ticker, run, {ticker: bars}, end=period.end
            )
            independent_rows.extend(rows)
            independent_summaries.append(summary)
            independent_tickers.append(
                {
                    "ticker": ticker,
                    **summary["metrics"],
                    "setups": len(run.setups),
                    "entries": len(run.entries),
                    "open_trades": summary["open_trades"],
                }
            )
        run = simulator.run(
            self.histories, start=period.start, end=period.end, spy=self.spy, sectors=self.sectors
        )
        summary, _ = report_run(directory, run, self.histories, end=period.end)
        summary["independent"] = {
            **stats(independent_rows),
            "prepared_tickers": len(independent_tickers),
            "tickers_with_setup": sum(r["setups"] > 0 for r in independent_tickers),
            "tickers_with_trade": sum(r["entries"] > 0 for r in independent_tickers),
            "positive_return_tickers": sum(r["total_return_pct"] > 0 for r in independent_tickers),
            "negative_return_tickers": sum(r["total_return_pct"] < 0 for r in independent_tickers),
            "open_trades": sum(r["open_trades"] for r in independent_tickers),
            "ambiguous_entry_target_order_count": sum(
                s["ambiguous_entry_target_order_count"] for s in independent_summaries
            ),
        }
        summary["preparation"] = self.preparation.copy()
        summary["prepared_tickers"] = len(self.histories)
        summary["metadata"] = {
            "strategy_id": "shauli-strat-v1",
            "version": 1,
            "timeframe": "DAILY",
            "direction": "LONG_ONLY",
            "start": period.start,
            "end": period.end,
            "actual_start": run.portfolio.equity_curve[0].trading_day,
            "actual_end": run.portfolio.equity_curve[-1].trading_day,
            "capital": Decimal("100000"),
            "max_positions": 10,
            "sizing": "equal-slot",
            "portfolio_ranking": "relative-strength-20",
            "cost": "COST_LOW",
            "slippage_bps_per_side": 5,
            "commission": 0,
            "dataset": build_shauli_protocol().dataset,
            "limitations": build_shauli_protocol().limitations,
            "final_open": "MARK_TO_CLOSE_NO_FORCE_LIQUIDATION",
            "no_operational_activation": True,
        }
        benchmark = BuyAndHoldSimulator().run(
            ticker="SPY",
            candles=self.spy,
            start=period.start,
            end=period.end,
            config=PortfolioConfig(initial_capital=Decimal("100000"), slippage_bps=Decimal("5")),
        )
        summary["spy"] = asdict(PortfolioPerformanceMetricsCalculator().calculate(benchmark))
        write_rows(directory / "independent_tickers.csv", independent_tickers)
        write_rows(directory / "independent_trades.csv", independent_rows)
        write_json_artifact(directory / "summary.json", summary)
        self.results[period] = summary
        print(
            f"Shauli {period}: return={summary['metrics']['total_return_pct']}, "
            f"completed={summary['metrics']['completed_trades']}",
            flush=True,
        )
        return summary

    def __call__(
        self,
        *,
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
        period: ResearchPeriod,
        fold_label: str | None,
    ) -> StrategyLabResultSummary:
        del fold_label
        if protocol != build_shauli_protocol() or configuration != protocol.candidates[0]:
            raise ValueError("undeclared Shauli protocol/configuration")
        return summary_to_lab(self.execute(period))


async def reference_context(source: FrozenDatasetMarketDataSource, output: Path) -> None:
    """Descriptive unchanged-strategy references; never used to select Shauli rules."""
    protocol = build_shauli_protocol()
    assert protocol.dataset is not None
    prior = BACKEND / "backtest_reports/achia_strat_ema20/ema_reference_2021-08-20_2024-12-31"
    summary_path = prior / "summary.json"
    ema = json.loads(summary_path.read_text(encoding="utf-8"))
    metadata = ema["metadata"]
    if (
        metadata["data"]["dataset_sha256"] != protocol.dataset.dataset_sha256
        or metadata["portfolio_configuration"]["sizing_policy"] != "equal-slot"
        or metadata["portfolio_configuration"]["slippage_bps"] != "5"
        or metadata["period_start"] != "2021-08-20"
        or metadata["period_end"] != "2024-12-31"
    ):
        raise ValueError("prior EMA reference is not configuration-identical")
    expected = json.loads((prior / "artifact_sha256.json").read_text(encoding="utf-8"))
    for name, digest in expected.items():
        if hashlib.sha256((prior / name).read_bytes()).hexdigest() != digest:
            raise ValueError("prior EMA artifact verification failed")
    service = MultiPortfolioBacktestService(
        source,
        source,
        source,
        Micho150Strategy(),
        stock_warmup_days=260,
        selection_policy=RelativeStrength20SelectionPolicy(),
        research_data_source=source,
    )
    print("Preparing unchanged Micho BOTH equal-slot development reference", flush=True)
    prepared = await service.prepare(
        start=protocol.development_period.start, end=protocol.development_period.end
    )
    result = service.run_prepared(prepared, config=MultiPortfolioConfig(slippage_bps=Decimal("5")))
    write_json_artifact(
        output / "references.json",
        {
            "ema_reused": {
                "source": str(summary_path.relative_to(BACKEND)),
                "sha256": expected["summary.json"],
                "metadata": metadata,
                "metrics": ema["metrics"],
                "diagnostics": ema["diagnostics"],
                "attribution": ema["attribution"],
            },
            "micho": {
                "metrics": result.metrics,
                "attribution": result.attribution,
                "failed_tickers": result.failed_tickers,
                "data": result.research_data,
                "configuration": "BOTH/RS20/equal-slot/100000/10/COST_LOW/no overlays",
                "average_loser_pct": sum(
                    (t.return_pct for t in result.portfolio.trades if t.pnl < 0), Decimal(0)
                )
                / max(1, sum(t.pnl < 0 for t in result.portfolio.trades)),
            },
        },
    )
    write_rows(
        output / "micho_reference_trades.csv",
        [{**asdict(t), "pnl": t.pnl, "return_pct": t.return_pct} for t in result.portfolio.trades],
    )


async def run(output: Path) -> None:
    freeze = json.loads((output / "freeze.json").read_text(encoding="utf-8"))
    if freeze["payload"] != freeze_payload():
        raise ValueError("source/protocol changed after freeze")
    with (output / "started.json").open("x", encoding="utf-8") as stream:
        json.dump({"started_at": datetime.now(UTC).isoformat(), "command": sys.argv}, stream)
    protocol = build_shauli_protocol()
    assert protocol.dataset is not None
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            )
            repository = ResearchDatasetRepository(session)
            service = ResearchDatasetService(repository)
            verification = await service.verify(protocol.dataset.snapshot_id)
            manifest = await service.get_manifest(protocol.dataset.snapshot_id)
            binding = DatasetBinding(
                verification.snapshot_id,
                verification.dataset_sha256,
                verification.universe_sha256,
                manifest.status == "FINALIZED",
                manifest.value_reproducible,
            )
            if binding != protocol.dataset or manifest.timeframe != "1Day":
                raise ValueError("frozen snapshot identity/timeframe mismatch")
            write_json_artifact(
                output / "dataset_verification.json", verification.model_dump(mode="json")
            )
            source = FrozenDatasetMarketDataSource(repository, protocol.dataset.snapshot_id)
            await reference_context(source, output)
            runner = ShauliResearchRunner(output, source)
            lab = StrategyLabService(runner=runner, dataset_resolver=lambda _: binding)
            experiment = lab.define(protocol)
            await runner.prepare(protocol.development_period)
            experiment = lab.run_development(experiment)
            checks = gate_checks(
                runner.results[protocol.development_period], verified=True, unexplained=0
            )
            write_json_artifact(output / "development_gates.json", checks)
            if not all(checks.values()):
                experiment = reject_stage(experiment, checks)
            else:
                experiment = lab.freeze_configuration(experiment, protocol.candidates[0])
                await runner.prepare(protocol.validation_period)
                experiment = lab.run_validation(experiment)
                checks = gate_checks(
                    runner.results[protocol.validation_period], verified=True, unexplained=0
                )
                write_json_artifact(output / "validation_gates.json", checks)
                if not all(checks.values()):
                    experiment = reject_stage(experiment, checks)
                else:
                    for fold in protocol.folds:
                        await runner.prepare(fold.period)
                        runner.execute(fold.period)
                    experiment = lab.classify(lab.run_folds(experiment))
            write_json_artifact(output / "experiment.json", experiment)
            if freeze["payload"] != freeze_payload():
                raise ValueError("source changed during frozen run")
            await session.rollback()
            write_json_artifact(
                output / "completed.json",
                {
                    "finished_at": datetime.now(UTC).isoformat(),
                    "source_unchanged": True,
                    "classification": experiment.classification,
                    "transaction": "READ ONLY; rolled back",
                    "validation_opened": experiment.validation_evidence is not None,
                    "folds_opened": bool(experiment.fold_evidence),
                },
            )
            write_json_artifact(
                output / "artifact_sha256.json",
                {
                    p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(output.rglob("*"))
                    if p.is_file()
                },
            )
            print(f"Completed: {experiment.classification}", flush=True)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen Shauli DAILY V1 research only")
    parser.add_argument("--output-dir", type=Path, default=Path("backtest_reports/shauli_strat_v1"))
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    if args.freeze_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        payload = freeze_payload()
        with (args.output_dir / "freeze.json").open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "payload": payload,
                    "frozen_at": datetime.now(UTC).isoformat(),
                    "git": asdict(capture_git_revision()),
                    "command": sys.argv,
                    "worktree": subprocess.check_output(
                        ["git", "status", "--porcelain=v1", "--untracked-files=all"], text=True
                    ),
                },
                stream,
                indent=2,
            )
        print(payload["protocol_fingerprint"])
        return
    loop_factory = (
        (lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
        if sys.platform == "win32"
        else asyncio.new_event_loop
    )
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(run(args.output_dir))


if __name__ == "__main__":
    main()
