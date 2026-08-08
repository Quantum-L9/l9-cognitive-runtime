"""Shared BaseModel helpers for fail-closed artifact models."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from l9_cognitive_runtime.models.canonical import canonical_json, sha256_digest
from l9_cognitive_runtime.models.errors import (
    InvalidValueError,
    ModelValidationError,
    UnknownFieldError,
)


class ArtifactModel(BaseModel):
    """Fail-closed artifact model with canonical JSON/digest helpers."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=False,
        validate_assignment=True,
    )

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise _translate_validation_error(exc) from exc

    def to_canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")

    def to_canonical_json(self) -> str:
        return canonical_json(self.to_canonical_dict())

    def sha256(self) -> str:
        return sha256_digest(self.to_canonical_dict())


def _translate_validation_error(exc: ValidationError) -> ModelValidationError:
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "<root>"
        etype = err.get("type", "")
        msg = err.get("msg", "validation failed")
        if etype == "extra_forbidden":
            return UnknownFieldError(msg, path=loc, details=err)
        return InvalidValueError(msg, path=loc, details=err)
    return InvalidValueError(str(exc), details=exc.errors())
