from uuid import uuid4

from alphapilot.cli.research_dataset import build_parser


def test_research_dataset_cli_supports_create_list_show_and_verify() -> None:
    parser = build_parser()
    created = parser.parse_args(
        [
            "create",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
            "--ticker",
            "AAPL",
            "--ticker",
            "MSFT",
        ]
    )
    assert created.command == "create"
    assert created.tickers == ["AAPL", "MSFT"]
    assert parser.parse_args(["list"]).command == "list"
    snapshot_id = uuid4()
    assert parser.parse_args(["show", str(snapshot_id)]).snapshot_id == snapshot_id
    assert parser.parse_args(["verify", str(snapshot_id)]).snapshot_id == snapshot_id
