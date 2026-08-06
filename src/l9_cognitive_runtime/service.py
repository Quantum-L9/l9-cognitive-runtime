"""In-memory cognitive runtime application service (L9CR-MCP-003/005)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from l9_cognitive_runtime.graph import derive_execution_graph
from l9_cognitive_runtime.models import (
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader, PackProvenance
from l9_cognitive_runtime.parsing import (
    load_yaml_file,
    require_known_kernels,
    require_non_empty_plan,
)


@dataclass(frozen=True)
class CompileRequest:
    """Inputs for an in-memory compile. No fixed repository output paths required."""

    mission: str
    task_type: str = "kernel_runtime_convergence"
    pack_root: Path | None = None
    pack_ref: str | Path | None = None
    constraints: tuple[str, ...] = (
        "model_agnostic",
        "kernel_first",
        "evidence_backed",
        "no_fake_validation",
    )
    desired_outputs: tuple[str, ...] = (
        "kernel_activation_plan",
        "execution_contract",
        "execution_graph",
        "validation_evidence",
        "adapter_render",
    )
    source_context: dict[str, Any] = field(default_factory=lambda: {"pack": "l9_cognitive_runtime"})
    unknowns: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeBundle:
    """Compiled runtime artifacts held entirely in memory."""

    intent: IntentContract
    execution: ExecutionContract
    validation: ValidationContract
    handoff: HandoffContract
    graph: ExecutionGraph
    provenance: PackProvenance

    def digests(self) -> dict[str, str]:
        return {
            "intent": self.intent.sha256(),
            "execution": self.execution.sha256(),
            "validation": self.validation.sha256(),
            "handoff": self.handoff.sha256(),
            "graph": self.graph.sha256(),
            "manifest": self.provenance.manifest_digest,
        }


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
    """Typed in-memory facade for CLI, tests, and future MCP adapters."""

    def __init__(self, repository: BundleRepository | None = None) -> None:
        self._repository = repository or LocalBundleRepository()

    def compile_runtime(self, request: CompileRequest) -> RuntimeBundle:
        if not request.mission.strip():
            raise InvalidValueError("mission must be non-empty", path="mission")
        pack_ref = request.pack_ref if request.pack_ref is not None else request.pack_root
        if pack_ref is None or str(pack_ref).strip() == "":
            raise InvalidValueError("explicit pack_ref required", path="pack_ref")
        pack = PackLoader().load(pack_ref)
        pack_root = self._repository.resolve_pack_root(Path(pack.provenance.root))
        provenance = pack.provenance
        intent = IntentContract.from_mapping(
            {
                "intent_id": "intent.runtime_convergence.v1",
                "mission": request.mission,
                "task_type": request.task_type,
                "constraints": list(request.constraints),
                "desired_outputs": list(request.desired_outputs),
                "source_context": dict(request.source_context),
                "unknowns": list(request.unknowns),
            }
        )
        execution = self._load_execution(pack_root)
        validation = self._load_validation(pack_root)
        handoff = self._load_handoff(pack_root)
        self._enforce_strict_activation(pack_root, execution)
        # Graph derives deterministically from the execution contract (MCP-006).
        graph = derive_execution_graph(execution)
        return RuntimeBundle(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            provenance=provenance,
        )

    def _load_execution(self, pack_root: Path) -> ExecutionContract:
        path = pack_root / "FINAL_EXECUTION_CONTRACT.yaml"
        return ExecutionContract.from_mapping(load_yaml_file(path))

    def _load_validation(self, pack_root: Path) -> ValidationContract:
        path = pack_root / "VALIDATION_CONTRACT.yaml"
        return ValidationContract.from_mapping(load_yaml_file(path))

    def _load_handoff(self, pack_root: Path) -> HandoffContract:
        path = pack_root / "HANDOFF_CONTRACT.yaml"
        return HandoffContract.from_mapping(load_yaml_file(path))

    def _enforce_strict_activation(self, pack_root: Path, execution: ExecutionContract) -> None:
        source = str(pack_root / "FINAL_EXECUTION_CONTRACT.yaml")
        if not execution.execution_sequence:
            require_non_empty_plan({}, source=source)
        if not execution.kernel_activation:
            require_non_empty_plan({}, source=source)
        available = self._discover_kernel_ids(pack_root)
        requested: list[str] = []
        for item in execution.kernel_activation:
            rel = item.strip().replace("\\", "/")
            candidate = (pack_root / rel).resolve()
            try:
                candidate.relative_to(pack_root.resolve())
            except ValueError as exc:
                raise InvalidValueError("kernel path escapes pack root", path=rel) from exc
            if candidate.is_file():
                available.add(rel)
                available.add(_kernel_id(rel))
            requested.append(rel if rel in available else _kernel_id(rel))
        require_known_kernels(requested, available, source="kernel_activation")

    def _discover_kernel_ids(self, pack_root: Path) -> set[str]:
        kernels_root = pack_root / "runtime" / "kernels"
        found: set[str] = set()
        if not kernels_root.is_dir():
            return found
        for path in kernels_root.rglob("*"):
            if path.suffix in {".yaml", ".yml"} and path.is_file():
                found.add(path.stem)
                found.add(path.name)
                found.add(str(path.relative_to(pack_root)).replace("\\", "/"))
        return found


def _kernel_id(item: str) -> str:
    text = item.strip().replace("\\", "/")
    name = Path(text).name
    if name.endswith((".yaml", ".yml")):
        return Path(name).stem
    return name
