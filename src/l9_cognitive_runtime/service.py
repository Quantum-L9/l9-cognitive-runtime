"""In-memory cognitive runtime application service (L9CR-MCP-003)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from l9_cognitive_runtime.models import (
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.models.errors import InvalidValueError, ModelValidationError
from l9_cognitive_runtime.parsing import load_yaml_file

if TYPE_CHECKING:
    from l9_cognitive_runtime.pack import PackProvenance


@dataclass(frozen=True)
class CompileRequest:
    """Inputs for an in-memory compile. No fixed repository output paths required."""

    mission: str
    task_type: str = "kernel_runtime_convergence"
    pack_root: Path | None = None
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
    provenance: PackProvenance | None = None

    def digests(self) -> dict[str, str]:
        payload = {
            "intent": self.intent.sha256(),
            "execution": self.execution.sha256(),
            "validation": self.validation.sha256(),
            "handoff": self.handoff.sha256(),
            "graph": self.graph.sha256(),
        }
        return payload


class BundleRepository(Protocol):
    """Dependency-injection seam for future pack/storage adapters."""

    def resolve_pack_root(self, pack_root: Path | None) -> Path: ...


class LocalBundleRepository:
    def resolve_pack_root(self, pack_root: Path | None) -> Path:
        if pack_root is None:
            # Default: repository root containing runtime/ and contracts/
            return Path.cwd()
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
        pack_root = self._repository.resolve_pack_root(request.pack_root)
        provenance = None
        try:
            from l9_cognitive_runtime.pack import PackLoader

            provenance = PackLoader().load(pack_root).provenance
        except (InvalidValueError, ModelValidationError, OSError, ValueError):
            # Pack verification is optional until an explicit pack_ref contract requires it.
            provenance = None
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
        execution = self._load_or_build_execution(pack_root, intent)
        validation = self._load_or_build_validation(pack_root)
        handoff = self._load_or_build_handoff(pack_root, intent)
        graph = self._build_graph(execution)
        return RuntimeBundle(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            provenance=provenance,
        )

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        return load_yaml_file(path)

    def _load_or_build_execution(
        self, pack_root: Path, intent: IntentContract
    ) -> ExecutionContract:
        path = pack_root / "FINAL_EXECUTION_CONTRACT.yaml"
        if path.is_file():
            try:
                return ExecutionContract.from_mapping(self._load_yaml(path))
            except ModelValidationError:
                raise
        # In-memory equivalent of the pack's universal execution contract shape.
        return ExecutionContract.from_mapping(
            {
                "contract_id": "FINAL_EXECUTION_CONTRACT",
                "contract_type": "universal_execution_contract",
                "source_activation_plan": (
                    "runtime/kernel_pipeline/planner/KERNEL_ACTIVATION_PLAN.example.yaml"
                ),
                "terminal_doctrine": "runtime/kernels/terminal/flawless_victory.contract.yaml",
                "objective": intent.mission,
                "authority_order": [
                    "user task",
                    "kernel activation plan",
                    "repo files",
                    "runtime pipeline contracts",
                    "tests and validation evidence",
                    "Unknown",
                ],
                "kernel_activation": [
                    "runtime/kernels/task/repo_auditor_kernel.yaml",
                    "runtime/kernels/terminal/flawless_victory.contract.yaml",
                ],
                "execution_sequence": [
                    "lock context",
                    "run constitutional preflight",
                    "execute terminal doctrine only after gates pass",
                ],
                "validation_requirements": [
                    "pipeline order validated",
                    "no fake validation",
                ],
                "output_contract": list(intent.desired_outputs),
                "adapter_targets": [
                    "claude_code",
                    "cursor",
                    "codex",
                    "chatgpt",
                    "human_operator",
                ],
                "version": "1.0.0",
                "metadata": {"compiled_by": "CognitiveRuntimeService"},
            }
        )

    def _load_or_build_validation(self, pack_root: Path) -> ValidationContract:
        path = pack_root / "VALIDATION_CONTRACT.yaml"
        if path.is_file():
            return ValidationContract.from_mapping(self._load_yaml(path))
        return ValidationContract.from_mapping(
            {
                "contract_id": "VALIDATION_CONTRACT",
                "contract_type": "validation_contract",
                "validation_ladder": ["format", "schema", "pipeline_order"],
                "evidence_required": ["status", "findings"],
                "allowed_statuses": [
                    "passed",
                    "failed",
                    "blocked",
                    "not_run",
                    "unknown",
                    "not_applicable_with_reason",
                ],
            }
        )

    def _load_or_build_handoff(self, pack_root: Path, intent: IntentContract) -> HandoffContract:
        path = pack_root / "HANDOFF_CONTRACT.yaml"
        if path.is_file():
            return HandoffContract.from_mapping(self._load_yaml(path))
        return HandoffContract.from_mapping(
            {
                "contract_id": "HANDOFF_CONTRACT",
                "contract_type": "handoff_contract",
                "handoff_summary": intent.mission,
                "loaded_context": ["runtime/kernels", "contracts"],
                "next_action": (
                    "Render the universal execution contract through the target adapter."
                ),
                "unknowns": list(intent.unknowns or []),
            }
        )

    def _build_graph(self, execution: ExecutionContract) -> ExecutionGraph:
        # Mirror runtime/execution_graph/build_execution_graph.DEFAULT_PHASES in memory.
        phases = [
            ("front_end_intake", "Phase 0 Front-End / Intent Intake", ["repo_auditor_kernel"]),
            (
                "semantic_preflight",
                "Phase 1 Semantic Analysis / Constitutional Preflight",
                ["K01", "K02", "K03", "K04", "K05"],
            ),
            ("strategic_expansion", "Phase 2 Strategic Expansion", ["prompt_compiler_kernel"]),
            (
                "architecture_synthesis",
                "Phase 3 Architecture Synthesis",
                ["l9_engine_build_kernel"],
            ),
            (
                "structural_validation",
                "Phase 4 Structural Validation",
                ["validate_eliminate_stubs"],
            ),
            ("optimization", "Phase 5 Optimization", ["recursive_improvement"]),
            ("global_optimization", "Phase 6 Global Optimization", ["recursive_leverage"]),
            ("emission", "Phase 7 Emission", ["flawless_victory"]),
        ]
        nodes = []
        edges = []
        for idx, (node_id, phase, kernels) in enumerate(phases):
            nodes.append(
                {
                    "id": node_id,
                    "phase": phase,
                    "kernel_refs": kernels,
                    "outputs": [f"{node_id.upper()}.md"],
                    "status": "planned",
                }
            )
            if idx > 0:
                edges.append(
                    {
                        "from": phases[idx - 1][0],
                        "to": node_id,
                        "reason": "phase_order",
                    }
                )
        return ExecutionGraph.from_mapping(
            {
                "graph_id": "l9_execution_graph.v1",
                "source_contract": execution.contract_id,
                "nodes": nodes,
                "edges": edges,
                "terminal_node": "emission",
                "validation_gates": [
                    "pipeline_order",
                    "kernel_roles",
                    "no_duplicate_active_kernels",
                    "phase_outputs",
                    "contract_compiler",
                    "execution_graph",
                ],
            }
        )
