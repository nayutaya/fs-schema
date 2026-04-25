from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from fs_schema import Schema, compile_to_bash


def _compile(schema_dict: dict[str, object]) -> str:
    return compile_to_bash(Schema.from_dict(schema_dict))


def _run_script(script: str, root: Path) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover - environment-specific
        pytest.skip("bash is not available")
    return subprocess.run(
        [bash, "-c", script, "fs-schema-compiled", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_compile_emits_shebang_and_header() -> None:
    script = _compile({"version": 0, "rules": []})

    assert script.startswith("#!/usr/bin/env bash\n")
    assert "fs_schema__case_sensitive=true" in script
    assert "fs_schema__follow_symlinks=false" in script
    assert script.rstrip().endswith('exit "$fs_schema__exit_code"')


def test_compile_require_path_succeeds_when_entry_exists(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "require", "path": "README.md", "kind": "file"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_compile_require_path_reports_missing(tmp_path: Path) -> None:
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "require", "path": "README.md", "kind": "file"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert "[missing] README.md does not exist" in result.stderr


def test_compile_require_path_reports_kind_mismatch(tmp_path: Path) -> None:
    (tmp_path / "README.md").mkdir()
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "require", "path": "README.md", "kind": "file"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert "[kind_mismatch] README.md has an unexpected kind" in result.stderr


def test_compile_forbid_path_reports_forbidden(tmp_path: Path) -> None:
    (tmp_path / "private.key").write_text("secret", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "forbid", "path": "private.key", "kind": "file"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert "[forbidden] private.key must not exist" in result.stderr


def test_compile_forbid_path_succeeds_when_entry_absent(tmp_path: Path) -> None:
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "forbid", "path": "private.key", "kind": "file"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0


def test_compile_implies_reports_implied_missing(tmp_path: Path) -> None:
    (tmp_path / "secrets.enc").write_text("data", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "implies",
                    "if": {"path": "secrets.enc", "exists": True},
                    "then": {"path": "secrets.key", "exists": True},
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert (
        "[implied_missing] secrets.key does not exist "
        "but is required because secrets.enc exists"
    ) in result.stderr


def test_compile_implies_succeeds_when_antecedent_absent(tmp_path: Path) -> None:
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "implies",
                    "if": {"path": "secrets.enc", "exists": True},
                    "then": {"path": "secrets.key", "exists": True},
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0


def test_compile_count_reports_below_minimum(tmp_path: Path) -> None:
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "count",
                    "select": {"path_regex": r"tests/.+\.py", "kind": "file"},
                    "minimum": 1,
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert (
        r"path_regex=tests/.+\.py, kind=file matched 0 entries, "
        "which is less than minimum=1"
    ) in result.stderr


def test_compile_count_reports_above_maximum(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "b.py").write_text("", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "count",
                    "select": {"path_regex": r"tests/.+\.py", "kind": "file"},
                    "maximum": 1,
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert (
        r"path_regex=tests/.+\.py, kind=file matched 2 entries, "
        "which is greater than maximum=1"
    ) in result.stderr


def test_compile_count_succeeds_within_bounds(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.py").write_text("", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "count",
                    "select": {"path_regex": r"tests/.+\.py", "kind": "file"},
                    "minimum": 1,
                    "maximum": 10,
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0


def test_compile_require_path_regex_succeeds(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "require",
                    "path_regex": r"README\.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0


def test_compile_require_path_regex_reports_missing(tmp_path: Path) -> None:
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "require",
                    "path_regex": r"README\.md",
                    "kind": "file",
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert r"[missing] path_regex=README\.md does not exist" in result.stderr


def test_compile_forbid_path_regex_reports_forbidden(tmp_path: Path) -> None:
    (tmp_path / "a.key").write_text("", encoding="utf-8")
    (tmp_path / "b.key").write_text("", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {
                    "type": "forbid",
                    "path_regex": r".+\.key",
                    "kind": "file",
                },
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 1
    assert "[forbidden] a.key must not exist" in result.stderr
    assert "[forbidden] b.key must not exist" in result.stderr


def test_compile_exits_with_code_2_when_root_is_not_a_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    script = _compile({"version": 0, "rules": []})

    result = _run_script(script, missing)

    assert result.returncode == 2
    assert "fs-schema: not a directory" in result.stderr


def test_compile_handles_paths_with_special_characters(tmp_path: Path) -> None:
    quoted = tmp_path / "it's-a-file.txt"
    quoted.write_text("", encoding="utf-8")
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "require", "path": "it's-a-file.txt", "kind": "file"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0


def test_compile_recognizes_symlinks_as_symlink_kind(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("", encoding="utf-8")
    link = tmp_path / "link.txt"
    os.symlink(target, link)
    script = _compile(
        {
            "version": 0,
            "rules": [
                {"type": "require", "path": "link.txt", "kind": "symlink"},
            ],
        },
    )

    result = _run_script(script, tmp_path)

    assert result.returncode == 0
