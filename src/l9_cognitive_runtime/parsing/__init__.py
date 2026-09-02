"""Strict YAML/JSON parsing — no silent fallbacks or guessed defaults."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from l9_cognitive_runtime.models.errors import InvalidValueError, ModelValidationError


class ParseErrorCode(StrEnum):
    MALFORMED_JSON = "MALFORMED_JSON"
    MALFORMED_YAML = "MALFORMED_YAML"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    ROOT_NOT_MAPPING = "ROOT_NOT_MAPPING"
    UNKNOWN_KERNEL = "UNKNOWN_KERNEL"
    EMPTY_PLAN = "EMPTY_PLAN"
    MISSING_REQUIRED = "MISSING_REQUIRED"


class StrictParseError(ModelValidationError):
    """Typed deterministic parse failure."""

    def __init__(
        self,
        message: str,
        *,
        code: ParseErrorCode,
        path: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message, path=path, details=details)
        self.code = code


def load_json_mapping(text: str, *, source: str = "<json>") -> dict[str, Any]:
    if not text.strip():
        raise StrictParseError(
            "empty JSON document", code=ParseErrorCode.EMPTY_DOCUMENT, path=source
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StrictParseError(
            "malformed JSON",
            code=ParseErrorCode.MALFORMED_JSON,
            path=source,
            details=str(exc),
        ) from exc
    if not isinstance(data, dict):
        raise StrictParseError(
            "JSON root must be an object",
            code=ParseErrorCode.ROOT_NOT_MAPPING,
            path=source,
        )
    return data


def load_yaml_mapping(text: str, *, source: str = "<yaml>") -> dict[str, Any]:
    if not text.strip():
        raise StrictParseError(
            "empty YAML document", code=ParseErrorCode.EMPTY_DOCUMENT, path=source
        )
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise StrictParseError(
            "malformed YAML",
            code=ParseErrorCode.MALFORMED_YAML,
            path=source,
            details=str(exc),
        ) from exc
    if data is None:
        raise StrictParseError(
            "empty YAML document", code=ParseErrorCode.EMPTY_DOCUMENT, path=source
        )
    if not isinstance(data, dict):
        raise StrictParseError(
            "YAML root must be a mapping",
            code=ParseErrorCode.ROOT_NOT_MAPPING,
            path=source,
        )
    return data


def confined_input_file(path: Path | str, *, allow_root: Path) -> Path:
    """Resolve an input file and prove it stays beneath an explicit root.

    File-bearing CLI and compatibility inputs are untrusted boundary data. An
    absolute path, ``..`` segment, or symlink must not turn a repository/pack
    read into arbitrary filesystem access. Callers choose the authority root;
    this function only proves the candidate remains inside it.
    """
    root = allow_root.expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise InvalidValueError(
            "input path escapes allow_root",
            path=str(path),
            details={"allow_root": str(root), "resolved": str(resolved)},
        ) from exc
    if not resolved.is_file():
        raise InvalidValueError("input file missing", path=str(resolved))
    return resolved


def load_yaml_file(path: Path, *, allow_root: Path) -> dict[str, Any]:
    resolved = confined_input_file(path, allow_root=allow_root)
    return load_yaml_mapping(resolved.read_text(encoding="utf-8"), source=str(resolved))


def require_non_empty_plan(plan: dict[str, Any], *, source: str) -> dict[str, Any]:
    if not plan:
        raise StrictParseError(
            "empty plans gain no authority",
            code=ParseErrorCode.EMPTY_PLAN,
            path=source,
        )
    return plan


def require_known_kernels(
    requested: list[str],
    available: set[str],
    *,
    source: str,
) -> list[str]:
    unknown = [name for name in requested if name not in available]
    if unknown:
        raise StrictParseError(
            "unknown kernels never substitute",
            code=ParseErrorCode.UNKNOWN_KERNEL,
            path=source,
            details={"unknown": unknown, "available": sorted(available)},
        )
    return requested
