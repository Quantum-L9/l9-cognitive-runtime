"""Kernel resolution: bind every activated kernel to a present, digested source.

Replaces the service's former static ``kernel_activation`` enforcement with a
fail-closed resolver over the live activation plan. Each binding records the
kernel identity, pack-relative source reference, and content digest — the seed
of the kernel liveness model (activation -> binding -> invocation -> output ->
consumption).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from l9_cognitive_runtime.parsing import ParseErrorCode, StrictParseError


@dataclass(frozen=True)
class KernelBinding:
    kernel_id: str
    source_ref: str
    source_digest: str


def _kernel_id(item: str) -> str:
    text = item.strip().replace("\\", "/")
    name = Path(text).name
    if name.endswith((".yaml", ".yml")):
        return Path(name).stem
    return name


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            bindings.append(
                KernelBinding(
                    kernel_id=_kernel_id(rel),
                    source_ref=rel,
                    source_digest=_sha256(candidate.read_bytes()),
                )
            )
        return bindings
