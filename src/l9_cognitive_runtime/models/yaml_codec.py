"""YAML codec that always round-trips through the canonical model serializer."""

from __future__ import annotations

from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from l9_cognitive_runtime.models.errors import InvalidValueError, ModelValidationError

T = TypeVar("T", bound=BaseModel)


def dump_yaml(model: BaseModel) -> str:
    """Serialize a model via its canonical dict, then YAML-dump that dict."""
    payload = model.to_canonical_dict()  # type: ignore[attr-defined]
    dumped: str = yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)
    return dumped


def load_yaml(model_type: type[T], text: str) -> T:
    """Load YAML into a mapping, then validate through the model constructor."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InvalidValueError("invalid YAML", details=str(exc)) from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise InvalidValueError("YAML root must be a mapping", details=type(data).__name__)
    try:
        return model_type.from_mapping(data)  # type: ignore[attr-defined, no-any-return]
    except ModelValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize to typed error
        raise ModelValidationError(str(exc), details=exc) from exc


def load_yaml_mapping(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise InvalidValueError("YAML root must be a mapping", details=type(data).__name__)
    return data
