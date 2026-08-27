from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from alphapilot.database.models.research_dataset import ResearchDatasetStatus
from alphapilot.database.session import get_db
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.strategy_lab.models import (
    CandidateConfiguration,
    DatasetBinding,
    ResearchPeriod,
    StrategyLabProtocol,
    StrategyLabResultSummary,
)
from alphapilot.strategy_lab.parsing import parse_protocol
from alphapilot.strategy_lab.reporting import write_json_artifact
from alphapilot.strategy_lab.service import StrategyLabService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and define a Strategy Lab protocol.")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument(
        "--stage",
        choices=(
            "validate-protocol",
            "defined",
            "development",
            "freeze",
            "validation",
            "folds",
            "classify",
        ),
        default="validate-protocol",
    )
    parser.add_argument("--freeze-configuration", default=None)
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="Structured deterministic result summaries for execution stages.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backtest_reports/strategy_lab/experiment.json"),
    )
    return parser


async def run(args: argparse.Namespace) -> None:
    protocol = parse_protocol(json.loads(args.protocol.read_text(encoding="utf-8")))
    if protocol.dataset is None:
        raise ValueError("formal Strategy Lab research requires a frozen dataset snapshot")
    database = get_db()
    session = await anext(database)
    try:
        snapshot = await ResearchDatasetRepository(session).get(protocol.dataset.snapshot_id)
        if snapshot is None:
            raise ValueError(f"Research dataset {protocol.dataset.snapshot_id} not found")
        binding = DatasetBinding(
            snapshot_id=snapshot.id,
            dataset_sha256=snapshot.dataset_sha256 or "",
            universe_sha256=snapshot.universe_sha256 or "",
            finalized=snapshot.status == ResearchDatasetStatus.FINALIZED.value,
            value_reproducible=snapshot.value_reproducible,
        )
        result_data = json.loads(args.results.read_text(encoding="utf-8")) if args.results else None
        service = StrategyLabService(
            runner=ArtifactResultRunner(result_data) if result_data is not None else _no_execution,
            dataset_resolver=lambda requested: (
                binding if requested.snapshot_id == binding.snapshot_id else requested
            ),
        )
        experiment = service.define(protocol)
        stage_order = {
            "validate-protocol": 0,
            "defined": 0,
            "development": 1,
            "freeze": 2,
            "validation": 3,
            "folds": 4,
            "classify": 5,
        }
        target = stage_order[args.stage]
        if target >= 1:
            if result_data is None:
                raise ValueError("execution stages require --results")
            experiment = service.run_development(experiment)
        if target >= 2:
            label = args.freeze_configuration
            if not label:
                raise ValueError("freeze and later stages require --freeze-configuration")
            configuration = next(
                (item for item in protocol.candidates if item.label == label),
                None,
            )
            if configuration is None:
                raise ValueError(f"Unknown freeze configuration: {label}")
            experiment = service.freeze_configuration(experiment, configuration)
        if target >= 3:
            experiment = service.run_validation(experiment)
        if target >= 4:
            experiment = service.run_folds(experiment)
        if target >= 5:
            experiment = service.classify(experiment)
        artifact = {
            "stage": args.stage,
            "experiment": experiment,
            "message": "Protocol validated against finalized Sprint 13 snapshot",
        }
        write_json_artifact(args.output, artifact)
        print(json.dumps({"experiment_id": experiment.experiment_id, "output": str(args.output)}))
    finally:
        await database.aclose()


def _no_execution(**_: object) -> StrategyLabResultSummary:
    raise RuntimeError("validate/defined CLI stages do not execute portfolio research")


class ArtifactResultRunner:
    """Read precomputed deterministic result summaries; never calculate strategy facts."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def __call__(
        self,
        *,
        protocol: StrategyLabProtocol,
        configuration: CandidateConfiguration,
        period: ResearchPeriod,
        fold_label: str | None,
    ) -> StrategyLabResultSummary:
        if fold_label is not None:
            value = self.data["folds"][fold_label]
        elif period == protocol.development_period:
            value = self.data["development"][configuration.label]
        elif period == protocol.validation_period:
            value = self.data["validation"][configuration.label]
        else:
            raise ValueError("result artifact period is not declared by the protocol")
        return _parse_result(value)


def _parse_result(value: dict[str, Any]) -> StrategyLabResultSummary:
    optional_decimal = {
        "cagr_pct",
        "sharpe_ratio",
        "calmar_ratio",
        "profit_factor",
        "top_5_positive_pnl_share_pct",
    }
    values: dict[str, Any] = {}
    for name, item in value.items():
        if name == "completed_trades":
            values[name] = int(item)
        elif name in optional_decimal and item is None:
            values[name] = None
        else:
            values[name] = Decimal(str(item))
    return StrategyLabResultSummary(**values)


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run(args), loop_factory=create_event_loop)


if __name__ == "__main__":
    main()
