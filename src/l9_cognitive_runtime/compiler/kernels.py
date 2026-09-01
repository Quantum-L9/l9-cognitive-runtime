"""Kernel resolution: bind every activated kernel to a present, digested source.

Replaces the service's former static ``kernel_activation`` enforcement with a
fail-closed resolver over the live activation plan. Each binding records the
kernel identity, pack-relative source reference, content digest, the kernel's
declared typed outputs (with their required consumers) — the seed of the kernel
liveness model (activation -> binding -> invocation -> output -> consumption) —
and the kernel's declared typed **context needs**.

Context needs are what make kernel selection mean something upstream
(INV-CTX-020): a selected kernel can actually demand context rather than being
copied into the compiled context as inert decoration. They are declarative and
colocated in the kernel's own semantic source, so they are digest-bound through
``source_digest`` without a second registry to drift against.

A kernel declares *what type* of context it needs. It never declares task
scope, runtime source results, or availability — those are not the kernel's to
know, and the requirement planner is what binds a need to the current task.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

from l9_cognitive_runtime.models.context import (
    AuthorityLevel,
    ContextKind,
    CoverageMode,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.parsing import ParseErrorCode, StrictParseError, load_yaml_file

# Consumer surfaces a kernel output may bind to. Anything else fails closed.
CONSUMER_SURFACES = (
    "execution_gate",
    "validation_contract",
    "handoff_contract",
    "convergence_gate",
    "adapter_renderer",
)

# The complete key set a declared context need may carry. Unknown keys fail
# closed rather than being ignored: a kernel trying to declare `scope_refs` or
# `available` is asserting something it cannot know, and silently dropping the
# key would make the kernel author believe it took effect.
CONTEXT_NEED_KEYS = frozenset(
    {
        "id",
        "context_kind",
        "required",
        "reason",
        "coverage",
        "minimum_authority",
        "required_semantic_keys",
    }
)


@dataclass(frozen=True)
class KernelOutput:
    output_id: str
    required: bool
    consumer_refs: tuple[str, ...]


@dataclass(frozen=True)
class KernelContextNeed:
    """A kernel's typed, task-independent declaration of context it needs."""

    need_id: str
    context_kind: ContextKind
    required: bool
    reason: str
    coverage: CoverageMode
    minimum_authority: AuthorityLevel
    required_semantic_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.need_id,
            "context_kind": self.context_kind.value,
            "required": self.required,
            "reason": self.reason,
            "coverage": self.coverage.value,
            "minimum_authority": self.minimum_authority.value,
            "required_semantic_keys": list(self.required_semantic_keys),
        }


@dataclass(frozen=True)
class KernelBinding:
    kernel_id: str
    source_ref: str
    source_digest: str
    outputs: tuple[KernelOutput, ...] = ()
    context_needs: tuple[KernelContextNeed, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kernel_id": self.kernel_id,
            "source_ref": self.source_ref,
            "source_digest": self.source_digest,
            "outputs": [
                {
                    "id": output.output_id,
                    "required": output.required,
                    "consumer_refs": list(output.consumer_refs),
                }
                for output in self.outputs
            ],
            "context_needs": [need.to_dict() for need in self.context_needs],
        }


def _kernel_id(item: str) -> str:
    text = item.strip().replace("\\", "/")
    name = Path(text).name
    if name.endswith((".yaml", ".yml")):
        return Path(name).stem
    return name


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_declared_outputs(
    kernel_doc: dict[str, Any], source_ref: str
) -> tuple[KernelOutput, ...]:
    """Parse a kernel file's declared typed outputs, fail closed on bad bindings."""
    raw_outputs = kernel_doc.get("typed_outputs")
    if raw_outputs is None:
        return ()
    if not isinstance(raw_outputs, list):
        raise InvalidValueError(
            "kernel outputs must be a list",
            path=source_ref,
        )
    parsed: list[KernelOutput] = []
    seen: set[str] = set()
    for entry in raw_outputs:
        if not isinstance(entry, dict):
            raise InvalidValueError("kernel output entry must be a mapping", path=source_ref)
        output_id = entry.get("id")
        required = entry.get("required")
        consumer_refs = entry.get("consumer_refs") or []
        if not isinstance(output_id, str) or not output_id.strip():
            raise InvalidValueError("kernel output requires a non-empty id", path=source_ref)
        if not isinstance(required, bool):
            raise InvalidValueError(
                "kernel output requires a boolean required flag", path=source_ref
            )
        if output_id in seen:
            raise InvalidValueError(
                "duplicate kernel output id", path=source_ref, details={"id": output_id}
            )
        if not isinstance(consumer_refs, list) or not all(
            isinstance(c, str) for c in consumer_refs
        ):
            raise InvalidValueError("kernel output consumer_refs must be strings", path=source_ref)
        unknown = [c for c in consumer_refs if c not in CONSUMER_SURFACES]
        if unknown:
            raise InvalidValueError(
                "kernel output consumer does not resolve",
                path=source_ref,
                details={"id": output_id, "unknown_consumers": unknown},
            )
        if required and not consumer_refs:
            raise InvalidValueError(
                "required kernel output has no consumer",
                path=source_ref,
                details={"id": output_id},
            )
        seen.add(output_id)
        parsed.append(
            KernelOutput(output_id=output_id, required=required, consumer_refs=tuple(consumer_refs))
        )
    return tuple(parsed)


_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _enum_value(
    raw: Any, enum_type: type[_EnumT], field_name: str, source_ref: str, need_id: str
) -> _EnumT:
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise InvalidValueError(
            f"kernel context need has an unknown {field_name}",
            path=source_ref,
            details={
                "id": need_id,
                field_name: raw,
                "allowed": sorted(enum_type.__members__.values()),
            },
        ) from exc


def _parse_context_needs(
    kernel_doc: dict[str, Any], source_ref: str
) -> tuple[KernelContextNeed, ...]:
    """Parse a kernel file's declared context needs, fail closed on bad shapes."""
    raw_needs = kernel_doc.get("context_needs")
    if raw_needs is None:
        return ()
    if not isinstance(raw_needs, list):
        raise InvalidValueError("kernel context_needs must be a list", path=source_ref)
    parsed: list[KernelContextNeed] = []
    seen: set[str] = set()
    for entry in raw_needs:
        if not isinstance(entry, dict):
            raise InvalidValueError("kernel context need must be a mapping", path=source_ref)
        unknown_keys = sorted(set(entry) - CONTEXT_NEED_KEYS)
        if unknown_keys:
            raise InvalidValueError(
                "kernel context need declares fields a kernel cannot know",
                path=source_ref,
                details={"unknown_keys": unknown_keys, "allowed": sorted(CONTEXT_NEED_KEYS)},
            )
        need_id = entry.get("id")
        if not isinstance(need_id, str) or not need_id.strip():
            raise InvalidValueError("kernel context need requires a non-empty id", path=source_ref)
        if need_id in seen:
            raise InvalidValueError(
                "duplicate kernel context need id", path=source_ref, details={"id": need_id}
            )
        required = entry.get("required")
        if not isinstance(required, bool):
            raise InvalidValueError(
                "kernel context need requires a boolean required flag",
                path=source_ref,
                details={"id": need_id},
            )
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidValueError(
                "kernel context need requires a non-empty reason",
                path=source_ref,
                details={"id": need_id},
            )
        keys = entry.get("required_semantic_keys") or []
        if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
            raise InvalidValueError(
                "kernel context need required_semantic_keys must be strings",
                path=source_ref,
                details={"id": need_id},
            )
        context_kind = _enum_value(
            entry.get("context_kind"), ContextKind, "context_kind", source_ref, need_id
        )
        coverage = _enum_value(entry.get("coverage"), CoverageMode, "coverage", source_ref, need_id)
        minimum_authority = _enum_value(
            entry.get("minimum_authority"),
            AuthorityLevel,
            "minimum_authority",
            source_ref,
            need_id,
        )
        if coverage is CoverageMode.SEMANTIC_KEYS and not keys:
            raise InvalidValueError(
                "semantic_keys coverage requires required_semantic_keys",
                path=source_ref,
                details={"id": need_id},
            )
        if coverage is not CoverageMode.SEMANTIC_KEYS and keys:
            raise InvalidValueError(
                "required_semantic_keys is only meaningful for semantic_keys coverage",
                path=source_ref,
                details={"id": need_id, "coverage": coverage.value},
            )
        seen.add(need_id)
        parsed.append(
            KernelContextNeed(
                need_id=need_id,
                context_kind=context_kind,
                required=required,
                reason=reason,
                coverage=coverage,
                minimum_authority=minimum_authority,
                required_semantic_keys=tuple(sorted(dict.fromkeys(keys))),
            )
        )
    return tuple(sorted(parsed, key=lambda need: need.need_id))


class KernelResolver:
    """Resolve activated kernel references against a pack root, fail closed."""

    def resolve(self, active_kernels: list[str], root: Path) -> list[KernelBinding]:
        resolved_root = root.resolve()
        bindings: list[KernelBinding] = []
        seen: set[str] = set()
        for item in active_kernels:
            rel = item.strip().replace("\\", "/")
            if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
                raise StrictParseError(
                    "kernel path escapes pack root",
                    code=ParseErrorCode.UNKNOWN_KERNEL,
                    path=rel,
                )
            candidate = (resolved_root / rel).resolve()
            try:
                candidate.relative_to(resolved_root)
            except ValueError as exc:
                raise StrictParseError(
                    "kernel path escapes pack root",
                    code=ParseErrorCode.UNKNOWN_KERNEL,
                    path=rel,
                ) from exc
            if not candidate.is_file():
                raise StrictParseError(
                    "activated kernel missing from pack",
                    code=ParseErrorCode.UNKNOWN_KERNEL,
                    path=rel,
                )
            if rel in seen:
                continue
            seen.add(rel)
            outputs: tuple[KernelOutput, ...] = ()
            context_needs: tuple[KernelContextNeed, ...] = ()
            if candidate.suffix in {".yaml", ".yml"}:
                kernel_doc = load_yaml_file(candidate)
                if kernel_doc is not None:
                    outputs = _parse_declared_outputs(kernel_doc, rel)
                    context_needs = _parse_context_needs(kernel_doc, rel)
            bindings.append(
                KernelBinding(
                    kernel_id=_kernel_id(rel),
                    source_ref=rel,
                    source_digest=_sha256(candidate.read_bytes()),
                    outputs=outputs,
                    context_needs=context_needs,
                )
            )
        return bindings
