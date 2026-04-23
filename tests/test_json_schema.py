from __future__ import annotations

from fs_schema.json_schema import (
    dump_entry_json_schema_path,
    fs_schema_json_schema_path,
)


def test_fs_schema_path_points_to_packaged_schema() -> None:
    schema_path = fs_schema_json_schema_path()

    assert schema_path.is_file()
    assert schema_path.parent.name == "schema"
    assert schema_path.name == "fs-schema.schema.yaml"


def test_dump_schema_path_points_to_packaged_schema() -> None:
    schema_path = dump_entry_json_schema_path()

    assert schema_path.is_file()
    assert schema_path.parent.name == "schema"
    assert schema_path.name == "fs-schema-dump-entry.schema.yaml"
