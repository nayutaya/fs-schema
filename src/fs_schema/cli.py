from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import click
import yaml

from fs_schema.compiler import compile_to_bash
from fs_schema.fs_dump import (
    InvalidDumpFileError,
    InvalidZipFileError,
    dump_as_jsonl,
    dump_filesystem,
    dump_zip_file,
    load_dump_file,
    write_dump_file,
)
from fs_schema.json_schema import (
    dump_entry_json_schema_path,
    fs_schema_json_schema_path,
    render_json_schema,
)
from fs_schema.schema_loader import InvalidSchemaFileError, load_schema_file
from fs_schema.validator import validate as validate_filesystem
from fs_schema.validator import validate_dump

EXISTING_FILE_PATH = click.Path(
    path_type=Path,
    exists=True,
    file_okay=True,
    dir_okay=False,
)
EXISTING_DIRECTORY_PATH = click.Path(
    path_type=Path,
    exists=True,
    file_okay=False,
    dir_okay=True,
)
OUTPUT_FILE_PATH = click.Path(
    path_type=Path,
    exists=False,
    file_okay=True,
    dir_okay=False,
)


@click.group()
def cli() -> None:
    pass


@cli.command("validate-schema", help="Validate the FS Schema file itself")
@click.argument("schema_path", type=EXISTING_FILE_PATH)
def validate_schema_command(schema_path: Path) -> None:
    try:
        load_schema_file(schema_path)
    except InvalidSchemaFileError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Schema file is valid: {schema_path}")


@cli.command("validate-dump", help="Validate the filesystem dump JSONL file itself")
@click.argument("dump_path", type=EXISTING_FILE_PATH)
def validate_dump_command(dump_path: Path) -> None:
    try:
        load_dump_file(dump_path)
    except InvalidDumpFileError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Dump file is valid: {dump_path}")


@cli.command("show-schema", help="Show the FS Schema JSON Schema")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Render the schema as JSON instead of YAML",
)
def show_schema_command(as_json: bool) -> None:
    try:
        click.echo(
            render_json_schema(fs_schema_json_schema_path(), as_json=as_json),
            nl=False,
        )
    except (OSError, yaml.YAMLError) as exc:
        raise click.ClickException(f"Failed to load JSON Schema: {exc}") from exc


@cli.command("show-dump-schema", help="Show the filesystem dump entry JSON Schema")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Render the schema as JSON instead of YAML",
)
def show_dump_schema_command(as_json: bool) -> None:
    try:
        click.echo(
            render_json_schema(dump_entry_json_schema_path(), as_json=as_json),
            nl=False,
        )
    except (OSError, yaml.YAMLError) as exc:
        raise click.ClickException(f"Failed to load JSON Schema: {exc}") from exc


@cli.command(help="Validate a file system tree against an FS Schema")
@click.option(
    "-s",
    "--schema",
    "schema_path",
    type=EXISTING_FILE_PATH,
    required=True,
    help="Path to the FS Schema YAML or JSON file",
)
@click.option(
    "-f",
    "--fs",
    "fs_path",
    type=EXISTING_DIRECTORY_PATH,
    required=False,
    help="Path to the file system root to validate",
)
@click.option(
    "-d",
    "--dump",
    "dump_path",
    type=EXISTING_FILE_PATH,
    required=False,
    help="Path to the filesystem dump JSONL file",
)
@click.option(
    "-z",
    "--zip",
    "zip_path",
    type=EXISTING_FILE_PATH,
    required=False,
    help="Path to the ZIP file to validate",
)
def validate_command(
    schema_path: Path,
    fs_path: Path | None,
    dump_path: Path | None,
    zip_path: Path | None,
) -> None:
    try:
        schema = load_schema_file(schema_path)
    except InvalidSchemaFileError as exc:
        raise click.ClickException(str(exc)) from exc

    input_count = sum(path is not None for path in (fs_path, dump_path, zip_path))
    if input_count != 1:
        raise click.UsageError("Specify exactly one of --fs, --dump, or --zip")

    try:
        if fs_path is not None:
            result = validate_filesystem(schema, fs_path)
            target = fs_path
        elif zip_path is not None:
            result = validate_dump(
                schema,
                {entry.path: entry for entry in dump_zip_file(zip_path)},
            )
            target = zip_path
        else:
            assert dump_path is not None
            result = validate_dump(schema, load_dump_file(dump_path))
            target = dump_path
    except (InvalidDumpFileError, InvalidZipFileError) as exc:
        raise click.ClickException(str(exc)) from exc

    if result.is_valid:
        click.echo(f"Validation succeeded: {target}")
        return

    for diagnostic in result.diagnostics:
        click.echo(f"[{diagnostic.code}] {diagnostic.message}", err=True)
    raise click.exceptions.Exit(1)


@cli.command(help="Compile an FS Schema into a standalone bash script")
@click.option(
    "-s",
    "--schema",
    "schema_path",
    type=EXISTING_FILE_PATH,
    required=True,
    help="Path to the FS Schema YAML or JSON file",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    required=True,
    help="Path to the output bash script, or - for stdout",
)
def compile_command(schema_path: Path, output_path: Path) -> None:
    try:
        schema = load_schema_file(schema_path)
    except InvalidSchemaFileError as exc:
        raise click.ClickException(str(exc)) from exc
    script = compile_to_bash(schema)
    if output_path == Path("-"):
        click.echo(script, nl=False)
        return
    output_path.write_text(script, encoding="utf-8")
    click.echo(f"Compiled bash script written: {output_path}")


@cli.command(help="Dump filesystem information for later validation")
@click.option(
    "-f",
    "--fs",
    "fs_path",
    type=EXISTING_DIRECTORY_PATH,
    required=False,
    help="Path to the file system root to dump",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    required=True,
    help="Path to the output JSONL file, or - for stdout",
)
@click.option(
    "-z",
    "--zip",
    "zip_path",
    type=EXISTING_FILE_PATH,
    required=False,
    help="Path to the ZIP file to dump",
)
def dump_command(
    fs_path: Path | None,
    output_path: Path,
    zip_path: Path | None,
) -> None:
    input_count = sum(path is not None for path in (fs_path, zip_path))
    if input_count != 1:
        raise click.UsageError("Specify exactly one of --fs or --zip")
    try:
        if fs_path is not None:
            entries = dump_filesystem(fs_path)
        else:
            assert zip_path is not None
            entries = dump_zip_file(zip_path)
    except InvalidZipFileError as exc:
        raise click.ClickException(str(exc)) from exc
    if output_path == Path("-"):
        click.echo(dump_as_jsonl(entries), nl=False)
        return
    write_dump_file(output_path, entries)
    click.echo(f"Filesystem dump written: {output_path}")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else None
    try:
        cli.main(args=args, prog_name="fs-schema", standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return exc.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
