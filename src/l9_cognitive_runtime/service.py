"""In-memory cognitive runtime application service (L9CR-MCP-003/005).

``CognitiveRuntimeService`` is the sole live composition root for fresh
missions (INV-001). Every public surface — CLI, MCP, tests — compiles through
``CompilePipeline``; static pack contracts (FINAL_EXECUTION_CONTRACT.yaml,
VALIDATION_CONTRACT.yaml, HANDOFF_CONTRACT.yaml) are museum artifacts and are
never loaded as fresh-mission truth (INV-009).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from l9_cognitive_runtime.compiler import CompilePipeline
from l9_cognitive_runtime.models.context import ContextSnapshot
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.types import CompileRequest, RuntimeBundle

__all__ = [
    "BundleRepository",
    "CognitiveRuntimeService",
    "CompileRequest",
    "ContextSnapshot",
    "LocalBundleRepository",
    "RuntimeBundle",
]


class BundleRepository(Protocol):
    """Dependency-injection seam for future pack/storage adapters."""

    def resolve_pack_root(self, pack_root: Path | None) -> Path: ...


class LocalBundleRepository:
    def resolve_pack_root(self, pack_root: Path | None) -> Path:
        if pack_root is None:
            raise InvalidValueError("pack_root is required", path="pack_root")
        root = pack_root.resolve()
        if not root.exists():
            raise InvalidValueError("pack_root does not exist", path=str(root))
        return root


class CognitiveRuntimeService:
    """Typed in-memory facade for CLI, tests, and MCP adapters."""

    def __init__(self, repository: BundleRepository | None = None) -> None:
        self._repository = repository or LocalBundleRepository()

    def compile_runtime(
        self,
        request: CompileRequest,
        *,
        context_snapshot: ContextSnapshot | None = None,
    ) -> RuntimeBundle:
        """Compile a fresh mission.

        ``context_snapshot`` is the governed context input (INV-CTX-007). It is
        deliberately a separate keyword rather than a ``CompileRequest`` field:
        raw caller hints in ``request.source_context`` must never be promotable
        into governed truth. ``None`` means an empty governed snapshot, which is
        what every pre-context caller gets.
        """
        if not request.mission.strip():
            raise InvalidValueError("mission must be non-empty", path="mission")
        pack_ref = request.pack_ref if request.pack_ref is not None else request.pack_root
        if pack_ref is None or str(pack_ref).strip() == "":
            raise InvalidValueError("explicit pack_ref required", path="pack_ref")
        pack = PackLoader().load(pack_ref)
        self._repository.resolve_pack_root(Path(pack.provenance.root))
        return CompilePipeline().compile(request, pack, context_snapshot=context_snapshot)
