"""YAML codec that always round-trips through the canonical model serializer."""

from __future__ import annotations

from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from l9_cognitive_runtime.models.errors import InvalidValueError, ModelValidationError

T = TypeVar("T", bound=BaseModel)


def dump_yaml(model: BaseModel) -> str:
    """Serialize a model via its canonical dict, then YAML-dump that dict."""
    payload = model.to_canonical_dict()  # type: ignore[attr-defined]
    dumped: str = yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)
    return dumped


def _load_mapping(text: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InvalidValueError("invalid YAML", details=str(exc)) from exc
    if data is None:
        raise InvalidValueError("YAML document is empty", details="null_root")
    if not isinstance(data, dict):
        raise InvalidValueError("YAML root must be a mapping", details=type(data).__name__)
    return data


def load_yaml(model_type: type[T], text: str) -> T:
    """Load YAML into a mapping, then validate through the model constructor."""
    data = _load_mapping(text)
    try:
        return model_type.from_mapping(data)  # type: ignore[attr-defined, no-any-return]
    except ModelValidationError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise ModelValidationError(str(exc), details=exc) from exc


def load_yaml_mapping(text: str) -> dict[str, Any]:
    return _load_mapping(text)
