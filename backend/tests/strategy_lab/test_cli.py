import json
from typing import Any

from alphapilot.cli.strategy_lab import ArtifactResultRunner, _parse_result, build_parser
from alphapilot.strategy_lab.parsing import parse_protocol
from alphapilot.strategy_lab.reporting import to_json_data, write_json_artifact


def test_cli_supports_every_governed_stage() -> None:
    parser = build_parser()
    for stage in (
        "validate-protocol",
        "defined",
        "development",
        "freeze",
        "validation",
        "folds",
        "classify",
    ):
        args = parser.parse_args(["--protocol", "protocol.json", "--stage", stage])
        assert args.stage == stage


def test_protocol_json_round_trip_is_machine_readable(protocol: Any) -> None:
    parsed = parse_protocol(to_json_data(protocol))
    assert parsed == protocol


def test_artifact_result_runner_selects_declared_stage_results(protocol: Any, result: Any) -> None:
    encoded = to_json_data(result)
    runner = ArtifactResultRunner(
        {
            "development": {item.label: encoded for item in protocol.candidates},
            "validation": {protocol.candidates[0].label: encoded},
            "folds": {fold.label: encoded for fold in protocol.folds},
        }
    )
    assert (
        runner(
            protocol=protocol,
            configuration=protocol.candidates[0],
            period=protocol.development_period,
            fold_label=None,
        )
        == result
    )
    assert (
        runner(
            protocol=protocol,
            configuration=protocol.candidates[0],
            period=protocol.folds[0].period,
            fold_label=protocol.folds[0].label,
        )
        == result
    )


def test_json_artifact_is_structured_and_deterministic(tmp_path: Any, protocol: Any) -> None:
    first = write_json_artifact(tmp_path / "first.json", protocol)
    second = write_json_artifact(tmp_path / "second.json", protocol)
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["protocol_version"] == 1


def test_parse_result_preserves_optional_nulls(result: Any) -> None:
    values = to_json_data(result)
    values["sharpe_ratio"] = None
    assert _parse_result(values).sharpe_ratio is None
