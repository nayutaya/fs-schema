from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Self


class EntryKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"


class RuleKind(StrEnum):
    REQUIRE = "require"
    FORBID = "forbid"
    IMPLIES = "implies"
    COUNT = "count"


def _normalize_relative_path(value: str) -> str:
    if value.endswith("/"):
        raise ValueError("path must not end with `/`")
    path = PurePosixPath(value)
    if not value or path.is_absolute():
        raise ValueError("path must be a relative path from the schema root")
    if "\\" in value:
        raise ValueError("path must use `/` as the separator")
    if ".." in path.parts:
        raise ValueError("path must not contain `..`")
    normalized = str(path)
    if normalized in {"", "."}:
        raise ValueError("path must be a concrete relative path")
    return normalized


def _require_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_string_key_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} must use string keys")
        normalized[key] = item
    return normalized


def _normalize_path_regex(value: str) -> str:
    if not value:
        raise ValueError("path_regex must not be empty")
    try:
        re.compile(value)
    except re.error as exc:
        raise ValueError("path_regex must be a valid regular expression") from exc
    return value


def _normalize_rule_path_selector(
    path: str | None,
    path_regex: str | None,
) -> tuple[str | None, str | None]:
    if path is None and path_regex is None:
        raise ValueError("exactly one of path or path_regex is required")
    if path is not None and path_regex is not None:
        raise ValueError("path and path_regex are mutually exclusive")
    if path is not None:
        return _normalize_relative_path(path), None
    assert path_regex is not None
    return None, _normalize_path_regex(path_regex)


def _normalize_implies_selector(path: str, path_regex: str | None) -> tuple[str, None]:
    if path_regex is not None:
        raise ValueError("implies only supports path")
    return _normalize_relative_path(path), None


def _require_optional_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _normalize_count_bounds(
    minimum: int | None,
    maximum: int | None,
) -> tuple[int | None, int | None]:
    if minimum is None and maximum is None:
        raise ValueError("at least one of minimum or maximum is required")
    if minimum is not None and minimum < 0:
        raise ValueError("minimum must be greater than or equal to 0")
    if maximum is not None and maximum < 0:
        raise ValueError("maximum must be greater than or equal to 0")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("minimum must be less than or equal to maximum")
    return minimum, maximum


@dataclass(slots=True, frozen=True)
class ValidationOptions:
    case_sensitive: bool = True
    follow_symlinks: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Self:
        if data is None:
            return cls()
        if not isinstance(data, Mapping):
            raise ValueError("options must be an object")
        return cls(
            case_sensitive=_require_bool(
                data.get("case_sensitive", True),
                field_name="options.case_sensitive",
            ),
            follow_symlinks=_require_bool(
                data.get("follow_symlinks", False),
                field_name="options.follow_symlinks",
            ),
        )


@dataclass(slots=True, frozen=True)
class RequireRule:
    id: str
    path: str | None
    path_regex: str | None = field(default=None, kw_only=True)
    kind: EntryKind
    type: RuleKind = field(default=RuleKind.REQUIRE, init=False)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("rule id must not be empty")
        normalized_path, normalized_path_regex = _normalize_rule_path_selector(
            self.path,
            self.path_regex,
        )
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "path_regex", normalized_path_regex)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError("rule must be an object")
        if data.get("type") != RuleKind.REQUIRE.value:
            raise ValueError("only type=require is supported in version 0")
        return cls(
            id=_require_string(data["id"], field_name="rules[].id"),
            path=_require_optional_string(data.get("path"), field_name="rules[].path"),
            path_regex=_require_optional_string(
                data.get("path_regex"),
                field_name="rules[].path_regex",
            ),
            kind=EntryKind(data["kind"]),
        )


@dataclass(slots=True, frozen=True)
class ForbidRule:
    id: str
    path: str | None
    path_regex: str | None = field(default=None, kw_only=True)
    kind: EntryKind
    type: RuleKind = field(default=RuleKind.FORBID, init=False)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("rule id must not be empty")
        normalized_path, normalized_path_regex = _normalize_rule_path_selector(
            self.path,
            self.path_regex,
        )
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "path_regex", normalized_path_regex)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError("rule must be an object")
        if data.get("type") != RuleKind.FORBID.value:
            raise ValueError("type must be forbid")
        return cls(
            id=_require_string(data["id"], field_name="rules[].id"),
            path=_require_optional_string(data.get("path"), field_name="rules[].path"),
            path_regex=_require_optional_string(
                data.get("path_regex"),
                field_name="rules[].path_regex",
            ),
            kind=EntryKind(data["kind"]),
        )


@dataclass(slots=True, frozen=True)
class ImpliesSelector:
    path: str
    exists: bool
    path_regex: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        normalized_path, normalized_path_regex = _normalize_implies_selector(
            self.path,
            self.path_regex,
        )
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "path_regex", normalized_path_regex)
        if self.exists is not True:
            raise ValueError("implies only supports exists=true")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, field_name: str) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError(f"{field_name} must be an object")
        if "path" not in data:
            raise ValueError(f"{field_name}.path is required")
        return cls(
            path=_require_string(data["path"], field_name=f"{field_name}.path"),
            exists=_require_bool(data.get("exists"), field_name=f"{field_name}.exists"),
            path_regex=_require_optional_string(
                data.get("path_regex"),
                field_name=f"{field_name}.path_regex",
            ),
        )


@dataclass(slots=True, frozen=True)
class ImpliesRule:
    id: str
    if_selector: ImpliesSelector
    then_selector: ImpliesSelector
    type: RuleKind = field(default=RuleKind.IMPLIES, init=False)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("rule id must not be empty")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError("rule must be an object")
        if data.get("type") != RuleKind.IMPLIES.value:
            raise ValueError("type must be implies")
        return cls(
            id=_require_string(data["id"], field_name="rules[].id"),
            if_selector=ImpliesSelector.from_dict(
                _require_string_key_mapping(data["if"], field_name="rules[].if"),
                field_name="rules[].if",
            ),
            then_selector=ImpliesSelector.from_dict(
                _require_string_key_mapping(data["then"], field_name="rules[].then"),
                field_name="rules[].then",
            ),
        )


@dataclass(slots=True, frozen=True)
class CountSelector:
    path_regex: str
    kind: EntryKind | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_regex", _normalize_path_regex(self.path_regex))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError("rules[].select must be an object")
        if "path_regex" not in data:
            raise ValueError("rules[].select.path_regex is required")
        return cls(
            path_regex=_require_string(
                data["path_regex"],
                field_name="rules[].select.path_regex",
            ),
            kind=(None if data.get("kind") is None else EntryKind(data["kind"])),
        )


@dataclass(slots=True, frozen=True)
class CountRule:
    id: str
    select: CountSelector
    minimum: int | None = None
    maximum: int | None = None
    type: RuleKind = field(default=RuleKind.COUNT, init=False)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("rule id must not be empty")
        normalized_minimum, normalized_maximum = _normalize_count_bounds(
            self.minimum,
            self.maximum,
        )
        object.__setattr__(self, "minimum", normalized_minimum)
        object.__setattr__(self, "maximum", normalized_maximum)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError("rule must be an object")
        if data.get("type") != RuleKind.COUNT.value:
            raise ValueError("type must be count")
        return cls(
            id=_require_string(data["id"], field_name="rules[].id"),
            select=CountSelector.from_dict(
                _require_string_key_mapping(
                    data["select"],
                    field_name="rules[].select",
                ),
            ),
            minimum=_require_optional_int(
                data.get("minimum"),
                field_name="rules[].minimum",
            ),
            maximum=_require_optional_int(
                data.get("maximum"),
                field_name="rules[].maximum",
            ),
        )


Rule = RequireRule | ForbidRule | ImpliesRule | CountRule


@dataclass(slots=True, frozen=True)
class Schema:
    version: int
    rules: tuple[Rule, ...]
    options: ValidationOptions = field(default_factory=ValidationOptions)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        if not isinstance(data, Mapping):
            raise ValueError("schema must be an object")
        version_value = data.get("version")
        if not isinstance(version_value, int) or isinstance(version_value, bool):
            raise ValueError("version must be an integer")
        if "rules" not in data:
            raise ValueError("rules is required")
        rules_value = data["rules"]
        if not isinstance(rules_value, list):
            raise ValueError("rules must be an array")
        version = version_value
        if version != 0:
            raise ValueError("only version=0 is supported")
        rules_list: list[Rule] = []
        for index, item in enumerate(rules_value):
            rules_list.append(
                _rule_from_dict(
                    _require_string_key_mapping(item, field_name="rule"),
                    index=index,
                ),
            )
        rules = tuple(rules_list)
        return cls(
            version=version,
            options=ValidationOptions.from_dict(data.get("options")),
            rules=rules,
        )


def _resolve_rule_id(data: Mapping[str, Any], *, index: int) -> str:
    id_value = data.get("id")
    if id_value is None:
        return f"rule{index}"
    return _require_string(id_value, field_name="rules[].id")


def _rule_from_dict(data: Mapping[str, Any], *, index: int) -> Rule:
    if not isinstance(data, Mapping):
        raise ValueError("rule must be an object")
    normalized_data = dict(data)
    normalized_data["id"] = _resolve_rule_id(data, index=index)
    match data.get("type"):
        case RuleKind.REQUIRE.value:
            return RequireRule.from_dict(normalized_data)
        case RuleKind.FORBID.value:
            return ForbidRule.from_dict(normalized_data)
        case RuleKind.IMPLIES.value:
            return ImpliesRule.from_dict(normalized_data)
        case RuleKind.COUNT.value:
            return CountRule.from_dict(normalized_data)
        case _:
            raise ValueError(
                "only type=require, type=forbid, type=implies, and type=count are supported in version 0",
            )


@dataclass(slots=True, frozen=True)
class Diagnostic:
    rule_id: str
    path: str
    code: str
    message: str
    expected_kind: EntryKind | None = None
    actual_kind: EntryKind | None = None


@dataclass(slots=True, frozen=True)
class ValidationResult:
    diagnostics: tuple[Diagnostic, ...]

    @property
    def is_valid(self) -> bool:
        return not self.diagnostics
