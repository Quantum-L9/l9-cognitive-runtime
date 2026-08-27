"""Kernel resolution: bind every activated kernel to a present, digested source.

Replaces the service's former static ``kernel_activation`` enforcement with a
fail-closed resolver over the live activation plan. Each binding records the
kernel identity, pack-relative source reference, content digest, and the
kernel's declared typed outputs (with their required consumers) — the seed of
the kernel liveness model (activation -> binding -> invocation -> output ->
consumption).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class KernelOutput:
    output_id: str
    required: bool
    consumer_refs: tuple[str, ...]


@dataclass(frozen=True)
class KernelBinding:
    kernel_id: str
    source_ref: str
    source_digest: str
    outputs: tuple[KernelOutput, ...] = ()

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
            KernelOutput(
                output_id=output_id, required=required, consumer_refs=tuple(consumer_refs)
            )
        )
    return tuple(parsed)


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
            if candidate.suffix in {".yaml", ".yml"}:
                kernel_doc = load_yaml_file(candidate)
                if kernel_doc is not None:
                    outputs = _parse_declared_outputs(kernel_doc, rel)
            bindings.append(
                KernelBinding(
                    kernel_id=_kernel_id(rel),
                    source_ref=rel,
                    source_digest=_sha256(candidate.read_bytes()),
                    outputs=outputs,
                )
            )
        return bindings
