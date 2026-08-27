from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from alphapilot.strategy_lab.models import CandidateConfiguration, StrategyLabProtocol


def canonical_data(value: object) -> Any:
    if is_dataclass(value):
        return {item.name: canonical_data(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): canonical_data(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [canonical_data(item) for item in value]
    if isinstance(value, (date, Decimal, UUID, Enum)):
        return str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported canonical identity value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    return json.dumps(canonical_data(value), sort_keys=True, separators=(",", ":"))


def experiment_identity(
    protocol: StrategyLabProtocol,
    frozen_configuration: CandidateConfiguration | None = None,
) -> str:
    payload = canonical_data(protocol)
    assert isinstance(payload, dict)
    specification = payload["specification"]
    assert isinstance(specification, dict)
    specification["allowed_selection_policies"] = sorted(
        specification["allowed_selection_policies"]
    )
    specification["allowed_sizing_policies"] = sorted(specification["allowed_sizing_policies"])
    specification["parameters"] = sorted(specification["parameters"], key=lambda item: item["name"])
    for declaration in specification["parameters"]:
        declaration["allowed_values"] = sorted(declaration["allowed_values"], key=canonical_json)
    payload["candidates"] = sorted(payload["candidates"], key=canonical_json)
    for candidate in payload["candidates"]:
        candidate["parameter_values"] = sorted(candidate["parameter_values"], key=canonical_json)
    payload["folds"] = sorted(payload["folds"], key=lambda item: item["label"])
    payload["frozen_configuration"] = canonical_data(frozen_configuration)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
