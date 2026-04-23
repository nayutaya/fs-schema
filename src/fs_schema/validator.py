from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from fs_schema.fs_dump import DumpEntry, dump_filesystem
from fs_schema.schema import (
    CountRule,
    Diagnostic,
    EntryKind,
    ForbidRule,
    ImpliesRule,
    RequireRule,
    Schema,
    ValidationResult,
)

PathRule = RequireRule | ForbidRule


def _rule_selector_text(rule: PathRule) -> str:
    if rule.path is not None:
        return rule.path
    assert rule.path_regex is not None
    return f"path_regex={rule.path_regex}"


def _normalize_root(root: str | Path) -> Path:
    return Path(root).expanduser().resolve()


def _coerce_schema(schema: Schema | Mapping[str, object]) -> Schema:
    if isinstance(schema, Schema):
        return schema
    return Schema.from_dict(schema)


def _count_selector_text(rule: CountRule) -> str:
    selector = f"path_regex={rule.select.path_regex}"
    if rule.select.kind is not None:
        selector = f"{selector}, kind={rule.select.kind.value}"
    return selector


def _validate_require_rule(
    rule: RequireRule,
    *,
    actual_kinds: tuple[tuple[str, EntryKind], ...],
) -> tuple[Diagnostic, ...]:
    if not actual_kinds:
        selector = _rule_selector_text(rule)
        return (
            Diagnostic(
                rule_id=rule.id,
                path=selector,
                code="missing",
                message=f"{selector} does not exist",
                expected_kind=rule.kind,
            ),
        )
    if any(actual_kind == rule.kind for _, actual_kind in actual_kinds):
        return ()
    return tuple(
        Diagnostic(
            rule_id=rule.id,
            path=path,
            code="kind_mismatch",
            message=f"{path} has an unexpected kind",
            expected_kind=rule.kind,
            actual_kind=actual_kind,
        )
        for path, actual_kind in actual_kinds
    )


def _validate_forbid_rule(
    rule: ForbidRule,
    *,
    actual_kinds: tuple[tuple[str, EntryKind], ...],
) -> tuple[Diagnostic, ...]:
    return tuple(
        Diagnostic(
            rule_id=rule.id,
            path=path,
            code="forbidden",
            message=f"{path} must not exist",
            expected_kind=rule.kind,
            actual_kind=actual_kind,
        )
        for path, actual_kind in actual_kinds
        if actual_kind == rule.kind
    )


def _validate_implies_rule(
    rule: ImpliesRule,
    *,
    antecedent_kind: EntryKind | None,
    consequent_kind: EntryKind | None,
) -> tuple[Diagnostic, ...]:
    if antecedent_kind is None or consequent_kind is not None:
        return ()
    return (
        Diagnostic(
            rule_id=rule.id,
            path=rule.then_selector.path,
            code="implied_missing",
            message=(
                f"{rule.then_selector.path} does not exist "
                f"but is required because {rule.if_selector.path} exists"
            ),
        ),
    )


def _validate_count_rule(
    rule: CountRule,
    *,
    actual_count: int,
) -> tuple[Diagnostic, ...]:
    selector = _count_selector_text(rule)
    if rule.minimum is not None and actual_count < rule.minimum:
        return (
            Diagnostic(
                rule_id=rule.id,
                path=selector,
                code="count_out_of_range",
                message=(
                    f"{selector} matched {actual_count} entries, "
                    f"which is less than minimum={rule.minimum}"
                ),
            ),
        )
    if rule.maximum is not None and actual_count > rule.maximum:
        return (
            Diagnostic(
                rule_id=rule.id,
                path=selector,
                code="count_out_of_range",
                message=(
                    f"{selector} matched {actual_count} entries, "
                    f"which is greater than maximum={rule.maximum}"
                ),
            ),
        )
    return ()


def _actual_kind_from_filesystem(
    root: Path,
    path: str,
    *,
    follow_symlinks: bool,
) -> EntryKind | None:
    target = root / Path(path)
    if not target.exists() and not target.is_symlink():
        return None
    if target.is_symlink():
        if not follow_symlinks:
            return EntryKind.SYMLINK
        try:
            resolved_target = target.resolve(strict=True)
        except FileNotFoundError:
            return EntryKind.SYMLINK
        return (
            _actual_kind_from_filesystem(
                resolved_target.parent,
                resolved_target.name,
                follow_symlinks=True,
            )
            or EntryKind.SYMLINK
        )
    if target.is_file():
        return EntryKind.FILE
    if target.is_dir():
        return EntryKind.DIRECTORY
    return None


def _actual_kind_from_dump(
    dump_entries: Mapping[str, DumpEntry],
    path: str,
    *,
    follow_symlinks: bool,
) -> EntryKind | None:
    entry = dump_entries.get(path)
    if entry is None:
        return None
    if follow_symlinks:
        return entry.resolved_kind
    return entry.kind


def _path_matches_exact(
    candidate: str,
    target: str,
    *,
    case_sensitive: bool,
) -> bool:
    if case_sensitive:
        return candidate == target
    return candidate.casefold() == target.casefold()


def _iter_matching_dump_entries(
    rule: PathRule,
    dump_entries: Mapping[str, DumpEntry],
    *,
    case_sensitive: bool,
    follow_symlinks: bool,
) -> tuple[tuple[str, EntryKind], ...]:
    if rule.path is not None:
        actual_kinds = tuple(
            (
                path,
                entry.resolved_kind if follow_symlinks else entry.kind,
            )
            for path, entry in sorted(dump_entries.items())
            if _path_matches_exact(path, rule.path, case_sensitive=case_sensitive)
        )
        return actual_kinds

    assert rule.path_regex is not None
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(rule.path_regex, flags=flags)
    return tuple(
        (
            path,
            entry.resolved_kind if follow_symlinks else entry.kind,
        )
        for path, entry in sorted(dump_entries.items())
        if pattern.fullmatch(path)
    )


def _count_matching_dump_entries(
    rule: CountRule,
    dump_entries: Mapping[str, DumpEntry],
    *,
    case_sensitive: bool,
    follow_symlinks: bool,
) -> int:
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(rule.select.path_regex, flags=flags)
    return sum(
        1
        for path, entry in dump_entries.items()
        if pattern.fullmatch(path)
        and (
            rule.select.kind is None
            or (entry.resolved_kind if follow_symlinks else entry.kind)
            == rule.select.kind
        )
    )


def validate(
    schema: Schema | Mapping[str, object],
    root: str | Path,
) -> ValidationResult:
    normalized_schema = _coerce_schema(schema)
    normalized_root = _normalize_root(root)
    use_dump_entries = any(
        (isinstance(rule, RequireRule | ForbidRule) and rule.path_regex is not None)
        or isinstance(rule, CountRule)
        for rule in normalized_schema.rules
    )
    use_dump_entries = use_dump_entries or not normalized_schema.options.case_sensitive
    if use_dump_entries:
        dump_entries = {entry.path: entry for entry in dump_filesystem(normalized_root)}
        return validate_dump(normalized_schema, dump_entries)
    diagnostics: list[Diagnostic] = []
    for rule in normalized_schema.rules:
        if isinstance(rule, RequireRule):
            assert rule.path is not None
            actual_kind = _actual_kind_from_filesystem(
                normalized_root,
                rule.path,
                follow_symlinks=normalized_schema.options.follow_symlinks,
            )
            diagnostics.extend(
                _validate_require_rule(
                    rule,
                    actual_kinds=(
                        () if actual_kind is None else ((rule.path, actual_kind),)
                    ),
                ),
            )
        elif isinstance(rule, ForbidRule):
            assert rule.path is not None
            actual_kind = _actual_kind_from_filesystem(
                normalized_root,
                rule.path,
                follow_symlinks=normalized_schema.options.follow_symlinks,
            )
            diagnostics.extend(
                _validate_forbid_rule(
                    rule,
                    actual_kinds=(
                        () if actual_kind is None else ((rule.path, actual_kind),)
                    ),
                ),
            )
        elif isinstance(rule, ImpliesRule):
            diagnostics.extend(
                _validate_implies_rule(
                    rule,
                    antecedent_kind=_actual_kind_from_filesystem(
                        normalized_root,
                        rule.if_selector.path,
                        follow_symlinks=normalized_schema.options.follow_symlinks,
                    ),
                    consequent_kind=_actual_kind_from_filesystem(
                        normalized_root,
                        rule.then_selector.path,
                        follow_symlinks=normalized_schema.options.follow_symlinks,
                    ),
                ),
            )
        else:
            raise AssertionError(f"unexpected rule type: {type(rule)!r}")
    return ValidationResult(diagnostics=tuple(diagnostics))


def validate_dump(
    schema: Schema | Mapping[str, object],
    dump_entries: Mapping[str, DumpEntry],
) -> ValidationResult:
    normalized_schema = _coerce_schema(schema)
    diagnostics: list[Diagnostic] = []
    for rule in normalized_schema.rules:
        if isinstance(rule, RequireRule):
            actual_kinds = _iter_matching_dump_entries(
                rule,
                dump_entries,
                case_sensitive=normalized_schema.options.case_sensitive,
                follow_symlinks=normalized_schema.options.follow_symlinks,
            )
            diagnostics.extend(
                _validate_require_rule(rule, actual_kinds=actual_kinds),
            )
        elif isinstance(rule, ForbidRule):
            actual_kinds = _iter_matching_dump_entries(
                rule,
                dump_entries,
                case_sensitive=normalized_schema.options.case_sensitive,
                follow_symlinks=normalized_schema.options.follow_symlinks,
            )
            diagnostics.extend(
                _validate_forbid_rule(rule, actual_kinds=actual_kinds),
            )
        elif isinstance(rule, CountRule):
            diagnostics.extend(
                _validate_count_rule(
                    rule,
                    actual_count=_count_matching_dump_entries(
                        rule,
                        dump_entries,
                        case_sensitive=normalized_schema.options.case_sensitive,
                        follow_symlinks=normalized_schema.options.follow_symlinks,
                    ),
                ),
            )
        else:
            diagnostics.extend(
                _validate_implies_rule(
                    rule,
                    antecedent_kind=_actual_kind_from_dump(
                        dump_entries,
                        rule.if_selector.path,
                        follow_symlinks=normalized_schema.options.follow_symlinks,
                    ),
                    consequent_kind=_actual_kind_from_dump(
                        dump_entries,
                        rule.then_selector.path,
                        follow_symlinks=normalized_schema.options.follow_symlinks,
                    ),
                ),
            )
    return ValidationResult(diagnostics=tuple(diagnostics))
