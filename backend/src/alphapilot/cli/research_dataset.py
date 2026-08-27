from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
from datetime import date
from uuid import UUID

from alphapilot.database.session import get_db
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.services.research_dataset import ResearchDatasetService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage immutable AlphaPilot research datasets.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="Create and finalize a frozen dataset.")
    create.add_argument("--start", type=date.fromisoformat, required=True)
    create.add_argument("--end", type=date.fromisoformat, required=True)
    create.add_argument("--label")
    create.add_argument("--benchmark", default="SPY")
    create.add_argument("--provider-expectation")
    create.add_argument("--feed-expectation")
    create.add_argument("--notes")
    create.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help="Repeat for explicit-universe mode; SPY is included as benchmark automatically.",
    )
    subparsers.add_parser("list", help="List frozen dataset manifests.")
    show = subparsers.add_parser("show", help="Show one manifest.")
    show.add_argument("snapshot_id", type=UUID)
    verify = subparsers.add_parser("verify", help="Recalculate and verify immutable hashes.")
    verify.add_argument("snapshot_id", type=UUID)
    return parser


async def run(args: argparse.Namespace) -> None:
    db_generator = get_db()
    session = await anext(db_generator)
    try:
        service = ResearchDatasetService(ResearchDatasetRepository(session))
        if args.command == "create":
            explicit = bool(args.tickers)
            result = await service.create_snapshot(
                start=args.start,
                end=args.end,
                universe_mode=(
                    ResearchDatasetService.EXPLICIT_TICKERS
                    if explicit
                    else ResearchDatasetService.CURRENT_UNIVERSE
                ),
                tickers=args.tickers,
                benchmark_ticker=args.benchmark,
                label=args.label,
                provider_expectation=args.provider_expectation,
                feed_expectation=args.feed_expectation,
                notes=args.notes,
            )
            payload: object = result.model_dump(mode="json")
        elif args.command == "list":
            manifests = await service.list_manifests()
            payload = [item.model_dump(mode="json") for item in manifests]
        elif args.command == "show":
            result = await service.get_manifest(args.snapshot_id)
            payload = result.model_dump(mode="json")
        else:
            verification = await service.verify(args.snapshot_id)
            payload = verification.model_dump(mode="json")
        print(json.dumps(payload, indent=2))
    finally:
        await db_generator.aclose()


def create_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run(args), loop_factory=create_event_loop)


if __name__ == "__main__":
    main()
