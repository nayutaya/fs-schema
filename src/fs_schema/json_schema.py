from __future__ import annotations

import json
from pathlib import Path

import yaml


def _schema_dir() -> Path:
    return Path(__file__).resolve().parent / "schema"


def fs_schema_json_schema_path() -> Path:
    return _schema_dir() / "fs-schema.schema.yaml"


def dump_entry_json_schema_path() -> Path:
    return _schema_dir() / "fs-schema-dump-entry.schema.yaml"


def render_json_schema(path: str | Path, *, as_json: bool) -> str:
    schema_path = Path(path)
    text = schema_path.read_text(encoding="utf-8")
    if not as_json:
        return text

    data = yaml.safe_load(text)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
