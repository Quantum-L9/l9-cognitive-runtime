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
