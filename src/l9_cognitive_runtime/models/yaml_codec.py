# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.src_l9_cognitive_runtime_models_yaml_codec__py
# title: yaml codec
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: src/l9_cognitive_runtime/models/yaml_codec.py
# content_hash: 68bd732990545cf1512ce789c712306c412a330e4ac7f4da2edf120b6ab59768
# token_cost_estimate: 400
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
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
