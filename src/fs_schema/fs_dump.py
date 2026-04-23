from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile, ZipInfo

from fs_schema.schema import EntryKind


class InvalidDumpFileError(ValueError):
    pass


class InvalidZipFileError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class DumpEntry:
    path: str
    kind: EntryKind
    resolved_kind: EntryKind

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DumpEntry:
        if not isinstance(data, Mapping):
            raise ValueError("dump entry must be an object")
        path = data.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("dump entry path must be a non-empty string")
        path_obj = PurePosixPath(path)
        if path_obj.is_absolute() or ".." in path_obj.parts or "\\" in path:
            raise ValueError("dump entry path must be a normalized relative path")
        kind = EntryKind(data["kind"])
        resolved_kind = EntryKind(data.get("resolved_kind", data["kind"]))
        return cls(path=str(path_obj), kind=kind, resolved_kind=resolved_kind)

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "kind": self.kind.value,
            "resolved_kind": self.resolved_kind.value,
        }


def _normalized_root(root: str | Path) -> Path:
    return Path(root).expanduser().resolve()


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _actual_kind(path: Path, *, follow_symlinks: bool) -> EntryKind | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        if not follow_symlinks:
            return EntryKind.SYMLINK
        try:
            target_kind = _actual_kind(path.resolve(strict=True), follow_symlinks=True)
        except FileNotFoundError:
            return EntryKind.SYMLINK
        return target_kind or EntryKind.SYMLINK
    if path.is_file():
        return EntryKind.FILE
    if path.is_dir():
        return EntryKind.DIRECTORY
    return None


def _iter_dump_entries(root: Path) -> Iterator[DumpEntry]:
    for path in sorted(root.rglob("*")):
        kind = _actual_kind(path, follow_symlinks=False)
        if kind is None:
            continue
        resolved_kind = _actual_kind(path, follow_symlinks=True) or kind
        yield DumpEntry(
            path=_relative_path(root, path),
            kind=kind,
            resolved_kind=resolved_kind,
        )


def _zip_info_kind(info: ZipInfo) -> EntryKind:
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        return EntryKind.SYMLINK
    if info.is_dir():
        return EntryKind.DIRECTORY
    return EntryKind.FILE


def _normalized_zip_entry_path(path: str) -> str:
    path_obj = PurePosixPath(path.rstrip("/"))
    normalized = str(path_obj)
    if (
        not normalized
        or path_obj.is_absolute()
        or ".." in path_obj.parts
        or "\\" in path
        or normalized == "."
    ):
        raise ValueError("zip entry path must be a normalized relative path")
    return normalized


def _iter_parent_directories(path: str) -> Iterator[str]:
    current = PurePosixPath(path).parent
    while str(current) not in {"", "."}:
        yield str(current)
        current = current.parent


def _resolved_kind_for_zip_path(
    zip_file: ZipFile,
    info: ZipInfo,
    infos_by_path: Mapping[str, ZipInfo],
) -> EntryKind:
    kind = _zip_info_kind(info)
    if kind is not EntryKind.SYMLINK:
        return kind
    try:
        target = zip_file.read(info).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return kind
    target_path = PurePosixPath(info.filename).parent / PurePosixPath(target)
    normalized_target = str(target_path)
    if (
        not normalized_target
        or target_path.is_absolute()
        or ".." in target_path.parts
        or normalized_target == "."
    ):
        return kind
    target_info = infos_by_path.get(normalized_target)
    if target_info is None:
        return kind
    target_kind = _zip_info_kind(target_info)
    if target_kind is EntryKind.SYMLINK:
        return kind
    return target_kind


def _iter_zip_dump_entries(zip_path: Path) -> Iterator[DumpEntry]:
    try:
        with ZipFile(zip_path) as zip_file:
            infos_by_path: dict[str, ZipInfo] = {}
            directory_paths: set[str] = set()
            for info in zip_file.infolist():
                if info.filename.endswith("/") and not info.is_dir():
                    continue
                normalized_path = _normalized_zip_entry_path(info.filename)
                infos_by_path[normalized_path] = info
                directory_paths.update(_iter_parent_directories(normalized_path))
            for directory_path in directory_paths:
                infos_by_path.setdefault(directory_path, ZipInfo(f"{directory_path}/"))

            entries: dict[str, DumpEntry] = {}
            for normalized_path, info in infos_by_path.items():
                path = _normalized_zip_entry_path(normalized_path)
                kind = _zip_info_kind(info)
                resolved_kind = _resolved_kind_for_zip_path(
                    zip_file,
                    info,
                    infos_by_path,
                )
                entries[path] = DumpEntry(
                    path=path,
                    kind=kind,
                    resolved_kind=resolved_kind,
                )
    except FileNotFoundError as exc:
        raise InvalidZipFileError(f"ZIP file does not exist: {zip_path}") from exc
    except OSError as exc:
        raise InvalidZipFileError(f"Failed to read ZIP file: {zip_path}") from exc
    except BadZipFile as exc:
        raise InvalidZipFileError(f"Failed to parse ZIP file: {zip_path}") from exc
    except ValueError as exc:
        raise InvalidZipFileError(f"Invalid ZIP entry: {zip_path}: {exc}") from exc

    for path in sorted(entries):
        yield entries[path]


def dump_filesystem(root: str | Path) -> tuple[DumpEntry, ...]:
    normalized_root = _normalized_root(root)
    return tuple(_iter_dump_entries(normalized_root))


def dump_zip_file(path: str | Path) -> tuple[DumpEntry, ...]:
    zip_path = Path(path)
    return tuple(_iter_zip_dump_entries(zip_path))


def dump_as_jsonl(entries: Iterable[DumpEntry]) -> str:
    lines = [json.dumps(entry.to_dict(), ensure_ascii=False) for entry in entries]
    text = "\n".join(lines)
    if lines:
        text += "\n"
    return text


def write_dump_file(path: str | Path, entries: Iterable[DumpEntry]) -> None:
    dump_path = Path(path)
    dump_path.write_text(dump_as_jsonl(entries), encoding="utf-8")


def load_dump_file(path: str | Path) -> Mapping[str, DumpEntry]:
    dump_path = Path(path)
    try:
        lines = dump_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise InvalidDumpFileError(f"Dump file does not exist: {dump_path}") from exc
    except OSError as exc:
        raise InvalidDumpFileError(f"Failed to read dump file: {dump_path}") from exc

    entries: dict[str, DumpEntry] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InvalidDumpFileError(
                f"Failed to parse dump JSONL at line {line_number}: {dump_path}",
            ) from exc
        try:
            entry = DumpEntry.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidDumpFileError(
                f"Invalid dump entry at line {line_number}: {dump_path}: {exc}",
            ) from exc
        if entry.path in entries:
            raise InvalidDumpFileError(
                f"Duplicate dump entry path at line {line_number}: {entry.path}",
            )
        entries[entry.path] = entry
    return entries
