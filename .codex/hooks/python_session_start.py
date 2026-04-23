from __future__ import annotations

from python_hook_lib import (
    python_snapshot,
    read_payload,
    repo_root,
    save_baseline,
    write_payload,
)


def main() -> None:
    payload = read_payload()
    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    if not session_id or not cwd:
        write_payload({})
        return

    root = repo_root(cwd)
    if root is None:
        write_payload({})
        return

    save_baseline(session_id, root, python_snapshot(root))
    write_payload({})


if __name__ == "__main__":
    main()
