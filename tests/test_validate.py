from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

import fs_schema


def test_validate_succeeds_when_required_entries_exist(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    (tmp_path / "src").mkdir()

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-readme",
                    "type": "require",
                    "path": "README.md",
                    "kind": "file",
                },
                {
                    "id": "require-src",
                    "type": "require",
                    "path": "src",
                    "kind": "directory",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_reports_missing_entries(tmp_path: Path) -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-readme",
                    "type": "require",
                    "path": "README.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="require-readme",
            path="README.md",
            code="missing",
            message="README.md does not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=None,
        ),
    )


def test_validate_supports_path_regex(tmp_path: Path) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "20260422.log").write_text("hello", encoding="utf-8")

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-log",
                    "type": "require",
                    "path_regex": r"logs/[0-9]{8}\.log",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_reports_missing_for_path_regex(tmp_path: Path) -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-log",
                    "type": "require",
                    "path_regex": r"logs/[0-9]{8}\.log",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="require-log",
            path=r"path_regex=logs/[0-9]{8}\.log",
            code="missing",
            message=r"path_regex=logs/[0-9]{8}\.log does not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=None,
        ),
    )


def test_validate_implies_succeeds_when_antecedent_is_absent(tmp_path: Path) -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "secret-needs-key",
                    "type": "implies",
                    "if": {
                        "path": "secrets.enc",
                        "exists": True,
                    },
                    "then": {
                        "path": "secrets.key",
                        "exists": True,
                    },
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_implies_reports_missing_consequent(tmp_path: Path) -> None:
    (tmp_path / "secrets.enc").write_text("hello", encoding="utf-8")
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "secret-needs-key",
                    "type": "implies",
                    "if": {
                        "path": "secrets.enc",
                        "exists": True,
                    },
                    "then": {
                        "path": "secrets.key",
                        "exists": True,
                    },
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="secret-needs-key",
            path="secrets.key",
            code="implied_missing",
            message=(
                "secrets.key does not exist but is required because secrets.enc exists"
            ),
            expected_kind=None,
            actual_kind=None,
        ),
    )


def test_validate_dump_implies_reports_missing_consequent() -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "secret-needs-key",
                    "type": "implies",
                    "if": {
                        "path": "secrets.enc",
                        "exists": True,
                    },
                    "then": {
                        "path": "secrets.key",
                        "exists": True,
                    },
                },
            ],
        },
    )
    dump_entries = {
        "secrets.enc": fs_schema.DumpEntry(
            path="secrets.enc",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="secret-needs-key",
            path="secrets.key",
            code="implied_missing",
            message=(
                "secrets.key does not exist but is required because secrets.enc exists"
            ),
            expected_kind=None,
            actual_kind=None,
        ),
    )


def test_schema_rejects_implies_selector_without_path() -> None:
    with pytest.raises(ValueError, match=r"rules\[\]\.if\.path is required"):
        fs_schema.Schema.from_dict(
            {
                "version": 0,
                "rules": [
                    {
                        "id": "secret-needs-key",
                        "type": "implies",
                        "if": {
                            "exists": True,
                        },
                        "then": {
                            "path": "secrets.key",
                            "exists": True,
                        },
                    },
                ],
            },
        )


def test_validate_count_succeeds_when_within_range(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "20260422.log").write_text("hello", encoding="utf-8")
    (logs_dir / "20260423.log").mkdir()
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "count-logs",
                    "type": "count",
                    "select": {
                        "path_regex": r"logs/[0-9]{8}\.log",
                        "kind": "file",
                    },
                    "minimum": 1,
                    "maximum": 2,
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_count_reports_below_minimum(tmp_path: Path) -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "count-logs",
                    "type": "count",
                    "select": {
                        "path_regex": r"logs/[0-9]{8}\.log",
                        "kind": "file",
                    },
                    "minimum": 1,
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="count-logs",
            path=r"path_regex=logs/[0-9]{8}\.log, kind=file",
            code="count_out_of_range",
            message=(
                r"path_regex=logs/[0-9]{8}\.log, kind=file matched 0 entries, "
                "which is less than minimum=1"
            ),
            expected_kind=None,
            actual_kind=None,
        ),
    )


def test_validate_dump_count_reports_above_maximum() -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "count-logs",
                    "type": "count",
                    "select": {
                        "path_regex": r"logs/[0-9]{8}\.log",
                        "kind": "file",
                    },
                    "maximum": 1,
                },
            ],
        },
    )
    dump_entries = {
        "logs/20260422.log": fs_schema.DumpEntry(
            path="logs/20260422.log",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
        "logs/20260423.log": fs_schema.DumpEntry(
            path="logs/20260423.log",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="count-logs",
            path=r"path_regex=logs/[0-9]{8}\.log, kind=file",
            code="count_out_of_range",
            message=(
                r"path_regex=logs/[0-9]{8}\.log, kind=file matched 2 entries, "
                "which is greater than maximum=1"
            ),
            expected_kind=None,
            actual_kind=None,
        ),
    )


def test_validate_count_ignores_entries_with_non_matching_kind(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "20260422.log").mkdir()
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "count-logs",
                    "type": "count",
                    "select": {
                        "path_regex": r"logs/[0-9]{8}\.log",
                        "kind": "file",
                    },
                    "minimum": 1,
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="count-logs",
            path=r"path_regex=logs/[0-9]{8}\.log, kind=file",
            code="count_out_of_range",
            message=(
                r"path_regex=logs/[0-9]{8}\.log, kind=file matched 0 entries, "
                "which is less than minimum=1"
            ),
            expected_kind=None,
            actual_kind=None,
        ),
    )


def test_validate_generates_rule_id_when_omitted(tmp_path: Path) -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "type": "require",
                    "path": "README.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="rule0",
            path="README.md",
            code="missing",
            message="README.md does not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=None,
        ),
    )


def test_schema_rejects_path_with_trailing_slash() -> None:
    with pytest.raises(ValueError, match=r"path must not end with `/`"):
        fs_schema.Schema.from_dict(
            {
                "version": 0,
                "rules": [
                    {
                        "id": "require-src",
                        "type": "require",
                        "path": "src/",
                        "kind": "directory",
                    },
                ],
            },
        )


def test_schema_rejects_implies_path_regex() -> None:
    with pytest.raises(ValueError, match="implies only supports path"):
        fs_schema.Schema.from_dict(
            {
                "version": 0,
                "rules": [
                    {
                        "id": "secret-needs-key",
                        "type": "implies",
                        "if": {
                            "path": "secrets.enc",
                            "path_regex": "secrets\\..*",
                            "exists": True,
                        },
                        "then": {
                            "path": "secrets.key",
                            "exists": True,
                        },
                    },
                ],
            },
        )


def test_schema_rejects_count_without_bounds() -> None:
    with pytest.raises(
        ValueError,
        match="at least one of minimum or maximum is required",
    ):
        fs_schema.Schema.from_dict(
            {
                "version": 0,
                "rules": [
                    {
                        "id": "count-logs",
                        "type": "count",
                        "select": {
                            "path_regex": r"logs/[0-9]{8}\.log",
                        },
                    },
                ],
            },
        )


def test_schema_rejects_count_when_minimum_exceeds_maximum() -> None:
    with pytest.raises(
        ValueError,
        match="minimum must be less than or equal to maximum",
    ):
        fs_schema.Schema.from_dict(
            {
                "version": 0,
                "rules": [
                    {
                        "id": "count-logs",
                        "type": "count",
                        "select": {
                            "path_regex": r"logs/[0-9]{8}\.log",
                        },
                        "minimum": 2,
                        "maximum": 1,
                    },
                ],
            },
        )


def test_validate_reports_kind_mismatch_for_directory(tmp_path: Path) -> None:
    (tmp_path / "README.md").mkdir()

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-readme",
                    "type": "require",
                    "path": "README.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="require-readme",
            path="README.md",
            code="kind_mismatch",
            message="README.md has an unexpected kind",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=fs_schema.EntryKind.DIRECTORY,
        ),
    )


def test_validate_reports_kind_mismatch_for_file(tmp_path: Path) -> None:
    (tmp_path / "src").write_text("hello", encoding="utf-8")

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-src",
                    "type": "require",
                    "path": "src",
                    "kind": "directory",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="require-src",
            path="src",
            code="kind_mismatch",
            message="src has an unexpected kind",
            expected_kind=fs_schema.EntryKind.DIRECTORY,
            actual_kind=fs_schema.EntryKind.FILE,
        ),
    )


def test_validate_identifies_symlink_kind(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("hello", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(target)

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-link",
                    "type": "require",
                    "path": "link.txt",
                    "kind": "symlink",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_succeeds_when_forbidden_entry_is_absent(tmp_path: Path) -> None:
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "forbid-private-key",
                    "type": "forbid",
                    "path": "private.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_reports_forbidden_entry(tmp_path: Path) -> None:
    (tmp_path / "private.key").write_text("secret", encoding="utf-8")

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "forbid-private-key",
                    "type": "forbid",
                    "path": "private.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="forbid-private-key",
            path="private.key",
            code="forbidden",
            message="private.key must not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=fs_schema.EntryKind.FILE,
        ),
    )


def test_validate_reports_forbidden_entry_for_path_regex(tmp_path: Path) -> None:
    (tmp_path / "private.key").write_text("secret", encoding="utf-8")

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "forbid-private-key",
                    "type": "forbid",
                    "path_regex": r".*\.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="forbid-private-key",
            path="private.key",
            code="forbidden",
            message="private.key must not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=fs_schema.EntryKind.FILE,
        ),
    )


def test_validate_ignores_forbid_rule_when_kind_differs(tmp_path: Path) -> None:
    (tmp_path / "private.key").mkdir()

    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "forbid-private-key",
                    "type": "forbid",
                    "path": "private.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate(schema, tmp_path)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_dump_succeeds_when_required_entries_exist() -> None:
    dump_entries: Mapping[str, fs_schema.DumpEntry] = {
        "README.md": fs_schema.DumpEntry(
            path="README.md",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
        "src": fs_schema.DumpEntry(
            path="src",
            kind=fs_schema.EntryKind.DIRECTORY,
            resolved_kind=fs_schema.EntryKind.DIRECTORY,
        ),
    }
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "require-readme",
                    "type": "require",
                    "path": "README.md",
                    "kind": "file",
                },
                {
                    "id": "require-src",
                    "type": "require",
                    "path": "src",
                    "kind": "directory",
                },
            ],
        },
    )

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_dump_uses_resolved_kind_when_following_symlinks() -> None:
    dump_entries: Mapping[str, fs_schema.DumpEntry] = {
        "link.txt": fs_schema.DumpEntry(
            path="link.txt",
            kind=fs_schema.EntryKind.SYMLINK,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "options": {"follow_symlinks": True},
            "rules": [
                {
                    "id": "require-link-target",
                    "type": "require",
                    "path": "link.txt",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_dump_reports_forbidden_entry() -> None:
    dump_entries: Mapping[str, fs_schema.DumpEntry] = {
        "private.key": fs_schema.DumpEntry(
            path="private.key",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "id": "forbid-private-key",
                    "type": "forbid",
                    "path": "private.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="forbid-private-key",
            path="private.key",
            code="forbidden",
            message="private.key must not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=fs_schema.EntryKind.FILE,
        ),
    )


def test_validate_dump_generates_rule_id_when_omitted() -> None:
    dump_entries: Mapping[str, fs_schema.DumpEntry] = {
        "private.key": fs_schema.DumpEntry(
            path="private.key",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "rules": [
                {
                    "type": "forbid",
                    "path": "private.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is False
    assert result.diagnostics == (
        fs_schema.Diagnostic(
            rule_id="rule0",
            path="private.key",
            code="forbidden",
            message="private.key must not exist",
            expected_kind=fs_schema.EntryKind.FILE,
            actual_kind=fs_schema.EntryKind.FILE,
        ),
    )


def test_validate_dump_supports_case_insensitive_exact_path() -> None:
    dump_entries: Mapping[str, fs_schema.DumpEntry] = {
        "README.md": fs_schema.DumpEntry(
            path="README.md",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "options": {"case_sensitive": False},
            "rules": [
                {
                    "id": "require-readme",
                    "type": "require",
                    "path": "readme.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_validate_dump_supports_case_insensitive_path_regex() -> None:
    dump_entries: Mapping[str, fs_schema.DumpEntry] = {
        "README.md": fs_schema.DumpEntry(
            path="README.md",
            kind=fs_schema.EntryKind.FILE,
            resolved_kind=fs_schema.EntryKind.FILE,
        ),
    }
    schema = fs_schema.Schema.from_dict(
        {
            "version": 0,
            "options": {"case_sensitive": False},
            "rules": [
                {
                    "id": "require-readme",
                    "type": "require",
                    "path_regex": r"readme\.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = fs_schema.validate_dump(schema, dump_entries)

    assert result.is_valid is True
    assert result.diagnostics == ()


def test_example_schema_is_valid_for_this_repository() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema = fs_schema.load_schema_file(repo_root / "examples" / "require.yaml")

    result = fs_schema.validate(schema, repo_root)

    assert result.is_valid is True
    assert result.diagnostics == ()
