from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

STATE_DIR = Path("/tmp/codex-python-hooks")


def read_payload() -> dict:
    try:
        return json.load(os.fdopen(0))
    except json.JSONDecodeError:
        return {}


def write_payload(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def repo_root(cwd: str) -> Path | None:
    current = Path(cwd).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip())


def tracked_python_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "*.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    files = [line for line in result.stdout.splitlines() if line]

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    files.extend(line for line in untracked.stdout.splitlines() if line)
    return sorted(set(files))


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def python_snapshot(root: Path) -> dict[str, str | None]:
    return {rel: file_hash(root / rel) for rel in tracked_python_files(root)}


def state_path(session_id: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe_session = session_id.replace("/", "_")
    return STATE_DIR / f"{safe_session}.json"


def save_baseline(session_id: str, root: Path, snapshot: dict[str, str | None]) -> None:
    path = state_path(session_id)
    path.write_text(
        json.dumps(
            {
                "repo_root": str(root),
                "snapshot": snapshot,
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
    )


def load_baseline(session_id: str) -> dict | None:
    path = state_path(session_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def changed_python_files(
    baseline: dict[str, str | None],
    current: dict[str, str | None],
) -> list[str]:
    paths = sorted(set(baseline) | set(current))
    return [path for path in paths if baseline.get(path) != current.get(path)]


def run_command(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=root,
        capture_output=True,
        text=True,
    )
