from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import selectors
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alphapilot.backtesting.achia_reporting import (
    completed_rows,
    diagnostics,
    entry_rows,
    recovery_rows,
    signal_rows,
    trade_summary,
    write_rows,
)
from alphapilot.backtesting.candidate_selection import RelativeStrength20SelectionPolicy
from alphapilot.backtesting.cost_scenarios import CostScenarioName, get_cost_scenario
from alphapilot.backtesting.multi_portfolio import MultiPortfolioSimulator
from alphapilot.backtesting.multi_portfolio_metrics import (
    MultiPortfolioPerformanceMetricsCalculator,
)
from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import (
    MultiPortfolioBacktestService,
    MultiPortfolioRunResult,
    PreparedMultiPortfolioData,
)
from alphapilot.backtesting.research_data_source import FrozenDatasetMarketDataSource
from alphapilot.backtesting.trade_management import ProtectiveStopPolicyName, TradeManagementConfig
from alphapilot.core.config import settings
from alphapilot.portfolio.risk import AverageTrueRangeCalculator
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.services.research_dataset import ResearchDatasetService, capture_git_revision
from alphapilot.strategy.achia_ema20 import AchiaStratEMA20Strategy
from alphapilot.strategy.ema20_pullback import EMA20PullbackStrategy
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy_lab.achia_ema20_protocol import (
    AchiaGateEvidence,
    build_achia_protocol,
    failed_achia_gates,
    reject_achia_stage,
)
from alphapilot.strategy_lab.identity import canonical_json, experiment_identity
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    DatasetBinding,
    ExperimentStage,
    ResearchPeriod,
    StrategyLabProtocol,
    StrategyLabResultSummary,
)
from alphapilot.strategy_lab.reporting import write_json_artifact
from alphapilot.strategy_lab.results import summarize_portfolio_result
from alphapilot.strategy_lab.service import StrategyLabService

BACKEND = Path(__file__).resolve().parents[3]


def source_hashes() -> dict[str, str]:
    paths: set[Path] = set()
    for directory in ("backtesting", "strategy", "strategy_lab", "research_data"):
        paths.update((BACKEND / "src/alphapilot" / directory).glob("*.py"))
    paths.update(
        BACKEND / "src/alphapilot" / name
        for name in (
            "cli/research_achia_ema20.py",
            "portfolio/risk.py",
            "market/session.py",
            "repositories/research_dataset.py",
            "services/research_dataset.py",
            "database/models/daily_candle.py",
            "database/models/research_dataset.py",
        )
    )
    return {
        path.relative_to(BACKEND).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def freeze_payload() -> dict[str, Any]:
    protocol = build_achia_protocol()
    return {
        "protocol": json.loads(canonical_json(protocol)),
        "protocol_fingerprint": experiment_identity(protocol),
        "configuration_fingerprint": experiment_identity(protocol, protocol.candidates[0]),
        "source_sha256": source_hashes(),
    }


def portfolio_config(*, achia: bool) -> MultiPortfolioConfig:
    cost = get_cost_scenario(CostScenarioName.COST_LOW)
    return MultiPortfolioConfig(
        initial_capital=Decimal("100000"),
        max_positions=10,
        commission_per_order=cost.commission_per_order,
        slippage_bps=cost.slippage_bps,
        trade_management=TradeManagementConfig(
            protective_stop=(
                ProtectiveStopPolicyName.ACHIA_ATR_PLUS_ENTRY_PERCENT
                if achia
                else ProtectiveStopPolicyName.CONTROL
            )
        ),
    )


def report_run(
    directory: Path,
    *,
    service: MultiPortfolioBacktestService,
    prepared: PreparedMultiPortfolioData,
    achia: bool,
    freeze: dict[str, Any],
) -> tuple[MultiPortfolioRunResult, dict[str, Any]]:
    config = portfolio_config(achia=achia)
    result = service.run_prepared(prepared, config=config)
    signals = signal_rows(prepared)
    trades = completed_rows(result.portfolio, prepared, signals)
    detail = diagnostics(result.portfolio, prepared, signals, trades)
    for name, rows in {
        "signals": signals,
        "trades": trades,
        "entries": entry_rows(result.portfolio),
        "equity": [asdict(item) for item in result.portfolio.equity_curve],
        "open_positions": [asdict(item) for item in result.portfolio.open_positions],
        "selection_audit": [asdict(item) for item in result.portfolio.selection_audit],
        "attribution": [asdict(item) for item in result.attribution.tickers],
        "sector_attribution": [asdict(item) for item in result.attribution.sectors],
        "stop_recovery": recovery_rows(trades, prepared),
    }.items():
        write_rows(directory / f"{name}.csv", rows)

    independent_trades: list[dict[str, Any]] = []
    independent_metrics = []
    independent_entries: list[dict[str, Any]] = []
    independent_configs = replace(config, max_positions=1)
    for ticker, backtest in sorted(prepared.backtests.items()):
        portfolio = MultiPortfolioSimulator(config=independent_configs).run(
            {ticker: backtest},
            ticker_sectors={ticker: prepared.ticker_sectors.get(ticker)},
            atr_values={
                (ticker, bar.trading_day): prepared.atr_values.get((ticker, bar.trading_day))
                for bar in backtest.bars
            },
        )
        independent_metrics.append(
            {
                "ticker": ticker,
                **asdict(MultiPortfolioPerformanceMetricsCalculator().calculate(portfolio)),
                "technical_buy_signals": sum(row["ticker"] == ticker for row in signals),
                "open_positions": len(portfolio.open_positions),
                "entries": len(portfolio.trades) + len(portfolio.open_positions),
                "rejected": portfolio.ranking_diagnostics.rejected_candidates,
            }
        )
        independent_trades.extend(completed_rows(portfolio, prepared, signals))
        independent_entries.extend(entry_rows(portfolio))
    write_rows(directory / "independent_ticker_metrics.csv", independent_metrics)
    write_rows(directory / "independent_trades.csv", independent_trades)
    write_rows(directory / "independent_entries.csv", independent_entries)
    write_rows(
        directory / "independent_stop_recovery.csv", recovery_rows(independent_trades, prepared)
    )
    independent_summary = trade_summary(independent_trades)

    attribution = result.attribution
    if abs(attribution.reconciliation_residual) > Decimal("0.00000001"):
        raise ValueError("final equity attribution reconciliation failed")
    curve = result.portfolio.equity_curve
    summary = {
        "metadata": {
            "strategy_id": "achia-strat-ema20-v1" if achia else "ema20-pullback-v1",
            "strategy_version": 1,
            "display_name": "Achia_strat_ema20" if achia else "EMA20 Pullback HYBRID 2%",
            "research_only": True,
            "period_start": prepared.start,
            "period_end": prepared.end,
            "actual_start": curve[0].trading_day if curve else None,
            "actual_end": curve[-1].trading_day if curve else None,
            "portfolio_configuration": config,
            "selection_policy": "relative-strength-20 (portfolio allocation only)",
            "cost_scenario": "COST_LOW",
            "data": prepared.research_data,
            "protocol_fingerprint": freeze["protocol_fingerprint"],
            "configuration_fingerprint": freeze["configuration_fingerprint"],
            "source_sha256": freeze["source_sha256"],
            "warnings": build_achia_protocol().limitations,
            "independent_analysis": (
                "$100000/ticker, one equal slot, no RS20 competition; pooled CAGR is undefined"
            ),
            "gross_return_definition": (
                "same executed holdings plus friction, NOT a zero-cost counterfactual"
            ),
        },
        "ticker_counts": {
            "successful": len(prepared.successful_tickers),
            "failed": len(prepared.failed_tickers),
            "failed_tickers": prepared.failed_tickers,
        },
        "metrics": result.metrics,
        "diagnostics": detail,
        "gross_return_pct": (attribution.gross_realized_pnl + attribution.gross_unrealized_pnl)
        / config.initial_capital
        * Decimal("100"),
        "attribution": attribution,
        "risk_diagnostics": result.portfolio.risk_diagnostics,
        "ranking_diagnostics": result.portfolio.ranking_diagnostics,
        "trade_management_diagnostics": result.portfolio.trade_management_diagnostics,
        "spy_metrics": result.spy_metrics,
        "independent_ticker_count": len(independent_metrics),
        "independent_pooled": independent_summary,
        "independent_entries": len(independent_entries),
        "independent_open_positions": sum(row["open_positions"] for row in independent_metrics),
    }
    write_json_artifact(directory / "summary.json", summary)
    write_json_artifact(
        directory / "artifact_sha256.json",
        {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.iterdir())
            if path.is_file()
        },
    )
    print(
        f"{directory.name}: return={result.metrics.total_return_pct:.4f}%, "
        f"DD={result.metrics.max_drawdown_pct:.4f}%, trades={result.metrics.completed_trades}; "
        f"independent trades={len(independent_trades)}",
        flush=True,
    )
    return result, summary


class ResearchRunner:
    def __init__(
        self, output: Path, source: FrozenDatasetMarketDataSource, freeze: dict[str, Any]
    ) -> None:
        self.output, self.source, self.freeze = output, source, freeze
        self.prepared: dict[
            tuple[ResearchPeriod, bool],
            tuple[MultiPortfolioBacktestService, PreparedMultiPortfolioData],
        ] = {}
        self.results: dict[
            tuple[ResearchPeriod, bool], tuple[MultiPortfolioRunResult, dict[str, Any]]
        ] = {}

    async def prepare(self, period: ResearchPeriod) -> None:
        for achia in (True, False):
            key = period, achia
            if key in self.prepared:
                continue
            print(
                f"Preparing {'Achia' if achia else 'EMA reference'} "
                f"{period.start}..{period.end}; frozen snapshot only",
                flush=True,
            )
            strategy = (
                AchiaStratEMA20Strategy()
                if achia
                else EMA20PullbackStrategy(
                    exit_mode=TrendExitMode.HYBRID, hybrid_trend_threshold_pct=Decimal("2")
                )
            )
            service = MultiPortfolioBacktestService(
                company_service=self.source,
                candle_service=self.source,
                universe_repository=self.source,
                strategy=strategy,
                stock_warmup_days=120,
                selection_policy=RelativeStrength20SelectionPolicy(),
                research_data_source=self.source,
            )
            prepared = await service.prepare(start=period.start, end=period.end)
            self.prepared[key] = service, prepared
            print(
                f"Prepared {len(prepared.successful_tickers)} tickers; "
                f"failed={len(prepared.failed_tickers)}",
                flush=True,
            )

    def execute(
        self, period: ResearchPeriod, *, achia: bool
    ) -> tuple[MultiPortfolioRunResult, dict[str, Any]]:
        key = period, achia
        if key not in self.results:
            service, prepared = self.prepared[key]
            name = f"{'achia' if achia else 'ema_reference'}_{period.start}_{period.end}"
            self.results[key] = report_run(
                self.output / name,
                service=service,
                prepared=prepared,
                achia=achia,
                freeze=self.freeze,
            )
        return self.results[key]

    def __call__(
        self,
        *,
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
        period: ResearchPeriod,
        fold_label: str | None,
    ) -> StrategyLabResultSummary:
        del fold_label
        if protocol != build_achia_protocol() or configuration != protocol.candidates[0]:
            raise ValueError("undeclared Achia protocol/configuration")
        return summarize_portfolio_result(self.execute(period, achia=True)[0])

    def gate_evidence(self, period: ResearchPeriod) -> AchiaGateEvidence:
        result, summary = self.results[period, True]
        detail = summary["diagnostics"]
        return AchiaGateEvidence(
            summarize_portfolio_result(result),
            summary["independent_pooled"]["expectancy_pct"],
            detail["native_boundary_coverage_pct"],
            detail["stop_distance_pct"]["p90"],
            detail["stop_distance_pct"]["max"],
            len(result.failed_tickers),
        )


async def run(output: Path) -> None:
    freeze_path = output / "freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze != freeze_payload():
        raise ValueError("protocol or source differs from pre-results freeze")
    if (output / "experiment.json").exists():
        raise ValueError("completed experiment exists; refusing automatic overwrite/rerun")
    protocol = build_achia_protocol()
    assert protocol.dataset is not None
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            repository = ResearchDatasetRepository(session)
            datasets = ResearchDatasetService(repository)
            verified = await datasets.verify(protocol.dataset.snapshot_id)
            manifest = await datasets.get_manifest(protocol.dataset.snapshot_id)
            resolved = DatasetBinding(
                verified.snapshot_id,
                verified.dataset_sha256,
                verified.universe_sha256,
                finalized=manifest.status == "FINALIZED",
                value_reproducible=manifest.value_reproducible,
            )
            if resolved != protocol.dataset:
                raise ValueError("authoritative snapshot mismatch; no mutable fallback")
            write_json_artifact(
                output / "dataset_verification.json", verified.model_dump(mode="json")
            )
            write_json_artifact(output / "run_git.json", asdict(capture_git_revision()))
            runner = ResearchRunner(
                output, FrozenDatasetMarketDataSource(repository, verified.snapshot_id), freeze
            )
            lab = StrategyLabService(runner=runner, dataset_resolver=lambda _: resolved)
            experiment = lab.define(protocol)
            await runner.prepare(protocol.development_period)
            experiment = lab.run_development(experiment)
            runner.execute(protocol.development_period, achia=False)
            failures = failed_achia_gates(runner.gate_evidence(protocol.development_period))
            if failures:
                experiment = reject_achia_stage(experiment, failures)
            else:
                experiment = lab.freeze_configuration(experiment, protocol.candidates[0])
                await runner.prepare(protocol.validation_period)
                experiment = lab.run_validation(experiment)
                runner.execute(protocol.validation_period, achia=False)
                failures = failed_achia_gates(
                    runner.gate_evidence(protocol.validation_period), validation=True
                )
                if failures:
                    experiment = reject_achia_stage(experiment, failures)
                else:
                    for fold in protocol.folds:
                        await runner.prepare(fold.period)
                        runner.execute(fold.period, achia=False)
                    experiment = lab.classify(lab.run_folds(experiment))
            write_json_artifact(output / "experiment.json", experiment)
            write_json_artifact(output / "gate_failures.json", failures)
            assert experiment.stage == ExperimentStage.CLASSIFIED
            print(f"Final classification: {experiment.classification}", flush=True)
            examples: list[dict[str, Any]] = []
            company_repository = CompanyRepository(session)
            candles_repository = DailyCandleRepository(session)
            for ticker in ("APA", "APO", "IBKR", "EOG", "AXON", "FAST", "AAPL", "MSFT"):
                company = await company_repository.get_by_ticker(ticker)
                latest = await candles_repository.get_latest(company.id) if company else None
                if company is None or latest is None:
                    examples.append({"ticker": ticker, "status": "UNAVAILABLE"})
                    continue
                candles = await candles_repository.get_history(
                    company.id, latest.trading_day - timedelta(days=120), latest.trading_day
                )
                evaluation = AchiaStratEMA20Strategy().evaluate_as_of(
                    candles, signal_day=latest.trading_day
                )
                ema20, ema50 = evaluation.ema20, evaluation.ema50
                examples.append(
                    {
                        "ticker": ticker,
                        "as_of": latest.trading_day,
                        "close": latest.close,
                        "ema20": ema20,
                        "ema50": ema50,
                        "trend_valid": ema20 > ema50 if ema20 and ema50 else None,
                        "entry_zone_valid": Decimal("0.90") * ema20
                        <= latest.close
                        <= Decimal("1.01") * ema20
                        if ema20
                        else None,
                        "distance_pct": (latest.close / ema20 - 1) * 100 if ema20 else None,
                        "atr14": AverageTrueRangeCalculator().calculate(
                            candles, signal_day=latest.trading_day
                        ),
                        "stop": "STOP PRICE NOT YET KNOWABLE UNTIL ENTRY FILL",
                        "status": "DESCRIPTIVE_STORED_COMPLETED_DATA_NOT_AN_ACTIONABLE_DECISION",
                    }
                )
            write_json_artifact(output / "current_examples.json", examples)
            if freeze != freeze_payload():
                raise ValueError("research source changed during experiment")
            write_json_artifact(
                output / "completed.json",
                {
                    "finished_at": datetime.now(UTC).isoformat(),
                    "protocol_fingerprint": freeze["protocol_fingerprint"],
                    "source_unchanged": True,
                    "database_transaction": (
                        "READ ONLY; rollback; no portfolio/Paper/News/candle/broker writes"
                    ),
                },
            )
            await session.rollback()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run only the frozen research-only Achia EMA20 V1 study."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("backtest_reports/achia_strat_ema20")
    )
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    if args.freeze_only:
        path = args.output_dir / "freeze.json"
        payload = freeze_payload()
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != payload:
            raise ValueError("existing freeze differs; refusing to replace frozen protocol")
        write_json_artifact(path, payload)
        print(
            json.dumps(
                {
                    key: payload[key]
                    for key in ("protocol_fingerprint", "configuration_fingerprint")
                },
                indent=2,
            )
        )
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
