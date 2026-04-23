# FS Schema

FS Schema is a Python library and command line tool for validating file and directory structures.

It lets you describe expected filesystem layouts in YAML or JSON, then validate a real directory tree, a ZIP archive, or a previously generated JSONL dump against that schema.

## Features

* Validate required and forbidden files, directories, and symbolic links
* Match paths by exact relative path or regular expression
* Express simple implication rules, such as requiring one path when another path exists
* Count matching entries with minimum and maximum bounds
* Validate local directories, ZIP archives, or JSONL filesystem dumps
* Export the built-in JSON Schemas for FS Schema documents and dump entries

## Installation

FS Schema requires Python 3.12 or later.

Install it from the Git repository with `uv`:

```sh
uv tool install git+https://github.com/nayutaya/fs-schema.git
```

You can also add it to a project:

```sh
uv add git+https://github.com/nayutaya/fs-schema.git
```

For local development, use `uv`:

```sh
uv sync
```

## Quick Start

Create a schema file:

```yaml
version: 0
rules:
  - type: require
    path: README.md
    kind: file
  - type: require
    path: src
    kind: directory
```

Validate a directory against it:

```sh
fs-schema validate --schema examples/require.yaml --fs .
```

The command exits with status code `0` when validation succeeds and status code `1` when the target does not match the schema.

## CLI Usage

Validate an FS Schema file:

```sh
fs-schema validate-schema examples/require.yaml
```

Validate a directory:

```sh
fs-schema validate --schema examples/require.yaml --fs .
```

Validate a ZIP archive:

```sh
fs-schema validate --schema examples/require.yaml --zip project.zip
```

Create a JSONL dump and validate it later:

```sh
fs-schema dump --fs . --output dump.jsonl
fs-schema validate --schema examples/require.yaml --dump dump.jsonl
```

Write a dump to standard output:

```sh
fs-schema dump --fs . --output -
```

Validate a dump file itself:

```sh
fs-schema validate-dump dump.jsonl
```

Print the built-in JSON Schemas:

```sh
fs-schema show-schema
fs-schema show-schema --json
fs-schema show-dump-schema
fs-schema show-dump-schema --json
```

## Schema Format

An FS Schema document has a `version` and a list of `rules`.

```yaml
version: 0
options:
  case_sensitive: true
  follow_symlinks: false
rules:
  - type: require
    path: README.md
    kind: file
  - type: forbid
    path_regex: (^|/)__pycache__$
    kind: directory
  - type: implies
    if:
      path: pyproject.toml
      exists: true
    then:
      path: README.md
      exists: true
  - type: count
    select:
      path_regex: tests/.+\.py
      kind: file
    minimum: 1
```

Supported entry kinds are:

* `file`
* `directory`
* `symlink`

Relative paths use `/` as the separator. Absolute paths, backslashes, `..` path segments, and paths ending with `/` are rejected.

The built-in JSON Schemas are distributed with the package:

* `src/fs_schema/schema/fs-schema.schema.yaml`
* `src/fs_schema/schema/fs-schema-dump-entry.schema.yaml`

## Python API

```python
from pathlib import Path

from fs_schema import load_schema_file, validate

schema = load_schema_file(Path("examples/require.yaml"))
result = validate(schema, Path("."))

if not result.is_valid:
    for diagnostic in result.diagnostics:
        print(f"[{diagnostic.code}] {diagnostic.message}")
```

## Development

Install dependencies:

```sh
mise install
uv sync --group dev
```

Run tests and checks:

```sh
uv run pytest
uv run ruff check --fix
uv run ruff format
uv run ty check
uv run lizard -l python src tests
```

Build the package:

```sh
uv build
```

## License

FS Schema is distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
