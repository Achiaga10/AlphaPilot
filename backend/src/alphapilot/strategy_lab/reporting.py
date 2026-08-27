from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


def to_json_data(value: object) -> Any:
    if is_dataclass(value):
        return {item.name: to_json_data(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_json_data(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_json_data(item) for item in value]
    if isinstance(value, (date, Decimal, UUID, Enum)):
        return str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def write_json_artifact(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json_data(value), indent=2), encoding="utf-8")
    return path
