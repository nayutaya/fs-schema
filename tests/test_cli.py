from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from click.testing import CliRunner

from fs_schema.cli import cli


def test_validate_schema_command_succeeds(tmp_path: Path) -> None:
    schema_path = tmp_path / "valid.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 0
    assert "Schema file is valid" in result.output


def test_validate_schema_command_accepts_json(tmp_path: Path) -> None:
    schema_path = tmp_path / "valid.json"
    schema_path.write_text(
        "\n".join(
            [
                "{",
                '  "version": 0,',
                '  "rules": [',
                "    {",
                '      "id": "require-readme",',
                '      "type": "require",',
                '      "path": "README.md",',
                '      "kind": "file"',
                "    }",
                "  ]",
                "}",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 0
    assert "Schema file is valid" in result.output


def test_validate_schema_command_accepts_rule_without_id(tmp_path: Path) -> None:
    schema_path = tmp_path / "valid-without-id.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 0
    assert "Schema file is valid" in result.output


def test_validate_schema_command_accepts_path_regex(tmp_path: Path) -> None:
    schema_path = tmp_path / "valid-path-regex.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: require",
                "    path_regex: README\\.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 0
    assert "Schema file is valid" in result.output


def test_validate_schema_command_accepts_implies_rule(tmp_path: Path) -> None:
    schema_path = tmp_path / "valid-implies.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: implies",
                "    if:",
                "      path: secrets.enc",
                "      exists: true",
                "    then:",
                "      path: secrets.key",
                "      exists: true",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 0
    assert "Schema file is valid" in result.output


def test_validate_schema_command_accepts_count_rule(tmp_path: Path) -> None:
    schema_path = tmp_path / "valid-count.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: count",
                "    select:",
                r"      path_regex: logs/[0-9]{8}\.log",
                "      kind: file",
                "    minimum: 1",
                "    maximum: 10",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 0
    assert "Schema file is valid" in result.output


def test_validate_schema_command_fails_for_invalid_schema(tmp_path: Path) -> None:
    schema_path = tmp_path / "invalid.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: ../README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "Invalid schema file" in result.output


def test_validate_schema_command_fails_for_path_with_trailing_slash(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "invalid-trailing-slash.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-src",
                "    type: require",
                "    path: src/",
                "    kind: directory",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "path must not end with `/`" in result.output


def test_validate_schema_command_fails_for_count_without_path_regex(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "invalid-count.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: count",
                "    select: {}",
                "    minimum: 1",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "rules[].select.path_regex is required" in result.output


def test_validate_schema_command_fails_for_implies_path_regex(tmp_path: Path) -> None:
    schema_path = tmp_path / "invalid-implies-path-regex.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: implies",
                "    if:",
                "      path: secrets.enc",
                "      path_regex: secrets\\..*",
                "      exists: true",
                "    then:",
                "      path: secrets.key",
                "      exists: true",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "implies only supports path" in result.output


def test_validate_schema_command_fails_when_path_and_path_regex_are_both_set(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "invalid-both-paths.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: require",
                "    path: README.md",
                "    path_regex: README\\.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "Invalid schema file" in result.output


def test_validate_schema_command_fails_for_invalid_yaml(tmp_path: Path) -> None:
    schema_path = tmp_path / "invalid-yaml.yaml"
    schema_path.write_text("version: [", encoding="utf-8")

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "Failed to parse YAML" in result.output


def test_validate_schema_command_fails_for_invalid_json(tmp_path: Path) -> None:
    schema_path = tmp_path / "invalid.json"
    schema_path.write_text('{"version": 0,', encoding="utf-8")

    result = CliRunner().invoke(cli, ["validate-schema", str(schema_path)])

    assert result.exit_code == 1
    assert "Failed to parse JSON" in result.output


def test_validate_dump_command_succeeds(tmp_path: Path) -> None:
    dump_path = tmp_path / "dump.jsonl"
    dump_path.write_text(
        '{"path": "README.md", "kind": "file", "resolved_kind": "file"}\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-dump", str(dump_path)])

    assert result.exit_code == 0
    assert f"Dump file is valid: {dump_path}" in result.output


def test_validate_dump_command_fails_for_invalid_entry(tmp_path: Path) -> None:
    dump_path = tmp_path / "dump.jsonl"
    dump_path.write_text(
        '{"path": "../README.md", "kind": "file", "resolved_kind": "file"}\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["validate-dump", str(dump_path)])

    assert result.exit_code == 1
    assert "Invalid dump entry at line 1" in result.output


def test_show_schema_command_outputs_yaml() -> None:
    result = CliRunner().invoke(cli, ["show-schema"])

    assert result.exit_code == 0
    assert '$schema: "https://json-schema.org/draft/2020-12/schema"' in result.output
    assert 'title: "FS Schema"' in result.output


def test_show_schema_command_outputs_json() -> None:
    result = CliRunner().invoke(cli, ["show-schema", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert data["title"] == "FS Schema"


def test_show_dump_schema_command_outputs_yaml() -> None:
    result = CliRunner().invoke(cli, ["show-dump-schema"])

    assert result.exit_code == 0
    assert '$schema: "https://json-schema.org/draft/2020-12/schema"' in result.output
    assert 'title: "FS Schema Dump Entry"' in result.output


def test_show_dump_schema_command_outputs_json() -> None:
    result = CliRunner().invoke(cli, ["show-dump-schema", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert data["title"] == "FS Schema Dump Entry"


def test_validate_command_succeeds(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    (fs_root / "README.md").write_text("hello", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--fs", str(fs_root)],
    )

    assert result.exit_code == 0
    assert f"Validation succeeded: {fs_root}" in result.output


def test_dump_command_writes_jsonl(tmp_path: Path) -> None:
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    (fs_root / "README.md").write_text("hello", encoding="utf-8")
    (fs_root / "src").mkdir()
    output_path = tmp_path / "dump.jsonl"

    result = CliRunner().invoke(
        cli,
        ["dump", "--fs", str(fs_root), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert f"Filesystem dump written: {output_path}" in result.output
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        '{"path": "README.md", "kind": "file", "resolved_kind": "file"}',
        '{"path": "src", "kind": "directory", "resolved_kind": "directory"}',
    ]


def test_dump_command_accepts_zip_input(tmp_path: Path) -> None:
    zip_path = tmp_path / "project.zip"
    with ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("src/main.py", "print('hello')\n")
    output_path = tmp_path / "dump.jsonl"

    result = CliRunner().invoke(
        cli,
        ["dump", "--zip", str(zip_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert f"Filesystem dump written: {output_path}" in result.output
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        '{"path": "src", "kind": "directory", "resolved_kind": "directory"}',
        '{"path": "src/main.py", "kind": "file", "resolved_kind": "file"}',
    ]


def test_dump_command_writes_jsonl_to_stdout(tmp_path: Path) -> None:
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    (fs_root / "README.md").write_text("hello", encoding="utf-8")
    (fs_root / "src").mkdir()

    result = CliRunner().invoke(
        cli,
        ["dump", "--fs", str(fs_root), "--output", "-"],
    )

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        '{"path": "README.md", "kind": "file", "resolved_kind": "file"}',
        '{"path": "src", "kind": "directory", "resolved_kind": "directory"}',
    ]


def test_validate_command_reports_diagnostics(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    fs_root = tmp_path / "project"
    fs_root.mkdir()

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--fs", str(fs_root)],
    )

    assert result.exit_code == 1
    assert "[missing] README.md does not exist" in result.output


def test_validate_command_rejects_missing_dump_path_at_cli_layer(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    missing_dump_path = tmp_path / "missing.jsonl"

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--dump", str(missing_dump_path)],
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_validate_command_reports_forbidden_diagnostics(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: forbid-private-key",
                "    type: forbid",
                "    path: private.key",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    (fs_root / "private.key").write_text("secret", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--fs", str(fs_root)],
    )

    assert result.exit_code == 1
    assert "[forbidden] private.key must not exist" in result.output


def test_dump_command_rejects_missing_filesystem_path_at_cli_layer(
    tmp_path: Path,
) -> None:
    missing_fs_path = tmp_path / "missing"
    output_path = tmp_path / "dump.jsonl"

    result = CliRunner().invoke(
        cli,
        ["dump", "--fs", str(missing_fs_path), "--output", str(output_path)],
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_dump_command_rejects_missing_zip_path_at_cli_layer(tmp_path: Path) -> None:
    zip_path = tmp_path / "missing.zip"
    output_path = tmp_path / "dump.jsonl"

    result = CliRunner().invoke(
        cli,
        ["dump", "--zip", str(zip_path), "--output", str(output_path)],
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_validate_command_accepts_short_options(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    (fs_root / "README.md").write_text("hello", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["validate", "-s", str(schema_path), "-f", str(fs_root)],
    )

    assert result.exit_code == 0
    assert f"Validation succeeded: {fs_root}" in result.output


def test_validate_command_accepts_dump_input(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-readme",
                "    type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    dump_path = tmp_path / "dump.jsonl"
    dump_path.write_text(
        '{"path": "README.md", "kind": "file", "resolved_kind": "file"}\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--dump", str(dump_path)],
    )

    assert result.exit_code == 0
    assert f"Validation succeeded: {dump_path}" in result.output


def test_validate_command_accepts_zip_input(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - id: require-src",
                "    type: require",
                "    path: src",
                "    kind: directory",
                "  - id: require-main",
                "    type: require",
                "    path: src/main.py",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    zip_path = tmp_path / "project.zip"
    with ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("src/main.py", "print('hello')\n")

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--zip", str(zip_path)],
    )

    assert result.exit_code == 0
    assert f"Validation succeeded: {zip_path}" in result.output


def test_validate_command_rejects_when_fs_and_dump_are_both_given(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text("version: 0\nrules: []\n", encoding="utf-8")
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    dump_path = tmp_path / "dump.jsonl"
    dump_path.write_text("", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "validate",
            "--schema",
            str(schema_path),
            "--fs",
            str(fs_root),
            "--dump",
            str(dump_path),
        ],
    )

    assert result.exit_code == 2
    assert "Specify exactly one of --fs, --dump, or --zip" in result.output


def test_validate_command_rejects_when_zip_and_dump_are_both_given(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text("version: 0\nrules: []\n", encoding="utf-8")
    zip_path = tmp_path / "project.zip"
    with ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("README.md", "hello\n")
    dump_path = tmp_path / "dump.jsonl"
    dump_path.write_text("", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "validate",
            "--schema",
            str(schema_path),
            "--zip",
            str(zip_path),
            "--dump",
            str(dump_path),
        ],
    )

    assert result.exit_code == 2
    assert "Specify exactly one of --fs, --dump, or --zip" in result.output


def test_validate_command_requires_fs_or_dump(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text("version: 0\nrules: []\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["validate", "--schema", str(schema_path)])

    assert result.exit_code == 2
    assert "Specify exactly one of --fs, --dump, or --zip" in result.output


def test_dump_command_rejects_when_fs_and_zip_are_both_given(tmp_path: Path) -> None:
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    zip_path = tmp_path / "project.zip"
    with ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("README.md", "hello\n")
    output_path = tmp_path / "dump.jsonl"

    result = CliRunner().invoke(
        cli,
        [
            "dump",
            "--fs",
            str(fs_root),
            "--zip",
            str(zip_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "Specify exactly one of --fs or --zip" in result.output


def test_validate_command_accepts_json_schema(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        "\n".join(
            [
                "{",
                '  "version": 0,',
                '  "rules": [',
                "    {",
                '      "id": "require-readme",',
                '      "type": "require",',
                '      "path": "README.md",',
                '      "kind": "file"',
                "    }",
                "  ]",
                "}",
            ],
        ),
        encoding="utf-8",
    )
    fs_root = tmp_path / "project"
    fs_root.mkdir()
    (fs_root / "README.md").write_text("hello", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["validate", "--schema", str(schema_path), "--fs", str(fs_root)],
    )

    assert result.exit_code == 0
    assert f"Validation succeeded: {fs_root}" in result.output


def test_help_output_is_in_english() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Show the FS Schema JSON Schema" in result.output
    assert "Show the filesystem dump entry JSON Schema" in result.output
    assert "Validate the FS Schema file itself" in result.output
    assert "Validate the filesystem dump JSONL file itself" in result.output
    assert "Validate a file system tree against an FS Schema" in result.output
    assert "Dump filesystem information for later validation" in result.output
    assert "Compile an FS Schema into a standalone bash script" in result.output


def test_validate_help_output_describes_options() -> None:
    result = CliRunner().invoke(cli, ["validate", "--help"])

    assert result.exit_code == 0
    assert "-s, --schema" in result.output
    assert "-f, --fs" in result.output
    assert "-d, --dump" in result.output
    assert "-z, --zip" in result.output
    assert "Path to the FS Schema YAML or JSON file" in result.output
    assert "Path to the file system root to validate" in result.output
    assert "Path to the filesystem dump JSONL file" in result.output
    assert "Path to the ZIP file to validate" in result.output


def test_dump_help_output_describes_options() -> None:
    result = CliRunner().invoke(cli, ["dump", "--help"])

    assert result.exit_code == 0
    assert "-f, --fs" in result.output
    assert "-o, --output" in result.output
    assert "-z, --zip" in result.output
    assert "Path to the file system root to dump" in result.output
    assert "Path to the output JSONL file, or - for stdout" in result.output
    assert "Path to the ZIP file to dump" in result.output


def test_show_schema_help_output_describes_options() -> None:
    result = CliRunner().invoke(cli, ["show-schema", "--help"])

    assert result.exit_code == 0
    assert "--json" in result.output
    assert "Render the schema as JSON instead of YAML" in result.output


def test_show_dump_schema_help_output_describes_options() -> None:
    result = CliRunner().invoke(cli, ["show-dump-schema", "--help"])

    assert result.exit_code == 0
    assert "--json" in result.output
    assert "Render the schema as JSON instead of YAML" in result.output


def test_compile_command_writes_bash_script(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "\n".join(
            [
                "version: 0",
                "rules:",
                "  - type: require",
                "    path: README.md",
                "    kind: file",
            ],
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "check.sh"

    result = CliRunner().invoke(
        cli,
        ["compile", "--schema", str(schema_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert f"Compiled bash script written: {output_path}" in result.output
    script = output_path.read_text(encoding="utf-8")
    assert script.startswith("#!/usr/bin/env bash\n")
    assert "README.md does not exist" in script


def test_compile_command_writes_script_to_stdout(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "version: 0\nrules: []\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["compile", "-s", str(schema_path), "-o", "-"],
    )

    assert result.exit_code == 0
    assert result.output.startswith("#!/usr/bin/env bash\n")
    assert 'exit "$fs_schema__exit_code"' in result.output


def test_compile_command_fails_for_invalid_schema(tmp_path: Path) -> None:
    schema_path = tmp_path / "invalid.yaml"
    schema_path.write_text(
        "version: 0\nrules:\n  - type: require\n    path: ../README.md\n    kind: file\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "check.sh"

    result = CliRunner().invoke(
        cli,
        ["compile", "-s", str(schema_path), "-o", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Invalid schema file" in result.output
    assert not output_path.exists()


def test_compile_help_output_describes_options() -> None:
    result = CliRunner().invoke(cli, ["compile", "--help"])

    assert result.exit_code == 0
    assert "-s, --schema" in result.output
    assert "-o, --output" in result.output
    assert "Path to the FS Schema YAML or JSON file" in result.output
    assert "Path to the output bash script, or - for stdout" in result.output
