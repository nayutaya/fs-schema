from __future__ import annotations

from python_hook_lib import (
    changed_python_files,
    load_baseline,
    python_snapshot,
    read_payload,
    repo_root,
    run_command,
    write_payload,
)


def main() -> None:
    payload = read_payload()
    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    stop_hook_active = payload.get("stop_hook_active", False)
    if not session_id or not cwd:
        write_payload({"continue": True})
        return

    if stop_hook_active:
        write_payload({"continue": True})
        return

    root = repo_root(cwd)
    if root is None:
        write_payload({"continue": True})
        return

    baseline_data = load_baseline(session_id)
    if baseline_data is None:
        write_payload({"continue": True})
        return

    baseline = baseline_data.get("snapshot", {})
    current = python_snapshot(root)
    files = changed_python_files(baseline, current)
    if not files:
        write_payload({"continue": True})
        return
    existing_files = [path for path in files if current.get(path) is not None]
    if not existing_files:
        write_payload({"continue": True})
        return

    check_fix = run_command(
        root,
        [
            "uv",
            "run",
            "--group",
            "dev",
            "--",
            "ruff",
            "check",
            "--fix",
            *existing_files,
        ],
    )
    format_fix = run_command(
        root,
        ["uv", "run", "--group", "dev", "--", "ruff", "format", *existing_files],
    )
    verify = run_command(
        root,
        ["uv", "run", "--group", "dev", "--", "ruff", "check", *existing_files],
    )
    ty_check = run_command(root, ["uv", "run", "--group", "dev", "--", "ty", "check"])

    if (
        check_fix.returncode == 0
        and format_fix.returncode == 0
        and verify.returncode == 0
        and ty_check.returncode == 0
    ):
        write_payload(
            {
                "continue": True,
                "systemMessage": (
                    f"Python hook ran successfully on {len(existing_files)} file(s): "
                    + ", ".join(existing_files)
                    + " (`ruff` and `ty check` passed in `dev` group)"
                ),
            },
        )
        return

    details = "\n".join(
        part
        for part in [
            check_fix.stdout,
            check_fix.stderr,
            format_fix.stdout,
            format_fix.stderr,
            verify.stdout,
            verify.stderr,
            ty_check.stdout,
            ty_check.stderr,
        ]
        if part.strip()
    )
    write_payload(
        {
            "decision": "block",
            "reason": (
                "Python files changed in this session. "
                "Codex ran `uv run --group dev -- ruff check --fix`, "
                "`uv run --group dev -- ruff format`, "
                "`uv run --group dev -- ruff check`, and "
                "`uv run --group dev -- ty check`, but issues remain.\n\n"
                f"{details}".strip()
            ),
        },
    )


if __name__ == "__main__":
    main()
