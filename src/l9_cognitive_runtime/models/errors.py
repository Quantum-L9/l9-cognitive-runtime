# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.src_l9_cognitive_runtime_models_errors__py
# title: errors
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: src/l9_cognitive_runtime/models/errors.py
# content_hash: c054fba2235dfa11ffc5f75d4d7fb6478d70b83238107300be88bacef08021d8
# token_cost_estimate: 233
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Typed validation errors for cognitive-runtime models."""

from __future__ import annotations

from typing import Any


class ModelValidationError(ValueError):
    """Base error for model parse/validation failures."""

    def __init__(self, message: str, *, path: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.details = details

    def __str__(self) -> str:
        if self.path:
            return f"{self.path}: {self.message}"
        return self.message


class UnknownFieldError(ModelValidationError):
    """Raised when input contains fields not declared on the model."""


class InvalidValueError(ModelValidationError):
    """Raised when a declared field fails type or constraint checks."""


class CanonicalizationError(ModelValidationError):
    """Raised when a value cannot be reduced to canonical JSON."""
