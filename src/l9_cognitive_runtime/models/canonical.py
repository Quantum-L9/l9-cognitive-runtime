"""Deterministic canonical JSON and SHA-256 digests."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from l9_cognitive_runtime.models.errors import CanonicalizationError


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _normalize(value[k]) for k in sorted(value.keys(), key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    raise CanonicalizationError(
        f"unsupported type for canonical JSON: {type(value).__name__}",
        details=type(value).__name__,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return UTF-8 JSON with sorted keys and separators ``(',', ':')``."""
    try:
        normalized = _normalize(value)
        text = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc
    return text.encode("utf-8")


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_digest(value: Any) -> str:
    """Return lowercase hex SHA-256 of the canonical JSON encoding."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
