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
from l9_cognitive_runtime.models.context import ContextPlan, ContextSnapshot
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader, RuntimePack
from l9_cognitive_runtime.types import CompileRequest, RuntimeBundle

__all__ = [
    "BundleRepository",
    "CognitiveRuntimeService",
    "CompileRequest",
    "ContextPlan",
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

    def _load_pack(self, request: CompileRequest) -> RuntimePack:
        if not request.mission.strip():
            raise InvalidValueError("mission must be non-empty", path="mission")
        pack_ref = request.pack_ref if request.pack_ref is not None else request.pack_root
        if pack_ref is None or str(pack_ref).strip() == "":
            raise InvalidValueError("explicit pack_ref required", path="pack_ref")
        pack = PackLoader().load(pack_ref)
        self._repository.resolve_pack_root(Path(pack.provenance.root))
        return pack

    def plan_context(
        self,
        request: CompileRequest,
        *,
        discovery_snapshot: ContextSnapshot | None = None,
    ) -> ContextPlan:
        """Compile the deterministic context-demand contract for an outer host.

        The supplied snapshot is discovery-only input. This method never acquires
        context; it exposes the exact typed requirements the outer host may fulfill
        before calling :meth:`compile_runtime` (INV-CTX-045).
        """
        pack = self._load_pack(request)
        return CompilePipeline().plan_context(request, pack, discovery_snapshot=discovery_snapshot)

    def compile_runtime(
        self,
        request: CompileRequest,
        *,
        context_snapshot: ContextSnapshot | None = None,
        expected_context_plan_id: str | None = None,
    ) -> RuntimeBundle:
        """Compile a fresh mission, optionally bound to a prior context plan.

        ``context_snapshot`` is the governed context input (INV-CTX-007). It is
        deliberately separate from ``CompileRequest`` so raw caller hints cannot
        become governed truth. When ``expected_context_plan_id`` is supplied, the
        compiler recomputes planning from the final snapshot and fails closed if
        route, kernels, discovery, requirements, or semantic sources changed
        (INV-CTX-046).
        """
        pack = self._load_pack(request)
        return CompilePipeline().compile(
            request,
            pack,
            context_snapshot=context_snapshot,
            expected_context_plan_id=expected_context_plan_id,
        )
