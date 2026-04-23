from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml

from fs_schema.schema import Schema


class InvalidSchemaFileError(ValueError):
    pass


def _load_raw_schema(schema_path: Path) -> object:
    text = schema_path.read_text(encoding="utf-8")
    if schema_path.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidSchemaFileError(
                f"Failed to parse JSON: {schema_path}",
            ) from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InvalidSchemaFileError(f"Failed to parse YAML: {schema_path}") from exc


def load_schema_file(path: str | Path) -> Schema:
    schema_path = Path(path)
    try:
        raw = _load_raw_schema(schema_path)
    except FileNotFoundError as exc:
        raise InvalidSchemaFileError(
            f"Schema file does not exist: {schema_path}",
        ) from exc
    except OSError as exc:
        raise InvalidSchemaFileError(
            f"Failed to read schema file: {schema_path}",
        ) from exc

    if not isinstance(raw, Mapping):
        raise InvalidSchemaFileError(
            "The top-level value of the schema file must be an object",
        )
    raw_mapping = cast("Mapping[str, Any]", raw)

    try:
        return Schema.from_dict(raw_mapping)
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidSchemaFileError(f"Invalid schema file: {exc}") from exc
