"""Service-level types shared by the facade and the live compiler spine.

Living here (rather than in ``service.py``) keeps the compiler package free of
an import cycle with the service facade while preserving the existing public
import path: ``service`` re-exports both names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from l9_cognitive_runtime.models import (
    CompiledTaskContext,
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.pack import PackProvenance


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
    semantic_digest: str
    packet: dict[str, Any]
    task_context: CompiledTaskContext

    def digests(self) -> dict[str, str]:
        return {
            "intent": self.intent.sha256(),
            "execution": self.execution.sha256(),
            "validation": self.validation.sha256(),
            "handoff": self.handoff.sha256(),
            "graph": self.graph.sha256(),
            "manifest": self.provenance.manifest_digest,
            "semantic": self.semantic_digest,
            # INV-CTX-027: computed from the finished context and carried here,
            # never stored inside the context itself.
            "context": self.task_context.sha256(),
        }
