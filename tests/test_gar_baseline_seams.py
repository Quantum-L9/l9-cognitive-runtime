"""PHASE-00 baseline locks for GAR Phase 2 integration (L9CR.GAR.PHASE2.INTEGRATION.001).

Each test pins a museum seam exactly as it exists today so later phases can
prove the seam is removed:

- A0001: semantically different missions share static pack artifacts.
- A0002: the task-and-architecture step substitutes ``prompt_compiler_kernel``.
- A0003: an unknown execution-sequence step collapses to the first
  ``kernel_activation`` entry.

Phase gate: these tests must reproduce current behavior with no production
change. PHASE-05 (structured execution graph) and PHASE-01 (single compiler
spine) convert them into liveness proofs.
"""

from __future__ import annotations

from pathlib import Path

from l9_cognitive_runtime.graph import derive_execution_graph
from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def test_a0001_different_missions_share_static_pack_artifacts(valid_pack: Path) -> None:
    """Two semantically different missions compile to identical static artifacts."""
    service = CognitiveRuntimeService()
    audit = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    audit_and_fix = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    audit_digests = audit.digests()
    fix_digests = audit_and_fix.digests()
    # Museum seam: execution/validation/handoff/graph are loaded statically from
    # the pack, so the missions share them byte-for-byte.
    assert audit_digests["execution"] == fix_digests["execution"]
    assert audit_digests["validation"] == fix_digests["validation"]
    assert audit_digests["handoff"] == fix_digests["handoff"]
    assert audit_digests["graph"] == fix_digests["graph"]


def test_a0002_task_and_architecture_step_substitutes_prompt_compiler(make_execution) -> None:
    """The selected task-and-architecture step maps to prompt_compiler_kernel.

    The contract's own ``kernel_activation`` entries are ignored for this step;
    the hard-coded phase map substitutes ``prompt_compiler_kernel``.
    """
    contract = ExecutionContract.from_mapping(
        make_execution(
            kernel_activation=["kernels/repo_auditor.yaml", "kernels/flawless_victory.yaml"],
            execution_sequence=["apply selected task and architecture kernels"],
        )
    )
    graph = derive_execution_graph(contract)
    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    assert node.id == "strategic_expansion"
    assert node.kernel_refs == ["prompt_compiler_kernel"]
    assert node.kernel_refs != list(contract.kernel_activation)


def test_a0003_unknown_step_collapses_to_first_kernel_activation(make_execution) -> None:
    """An unknown execution-sequence step collapses to ``kernel_activation[:1]``."""
    contract = ExecutionContract.from_mapping(
        make_execution(
            kernel_activation=["kernels/repo_auditor.yaml", "kernels/flawless_victory.yaml"],
            execution_sequence=["a completely novel step nobody has heard of"],
        )
    )
    graph = derive_execution_graph(contract)
    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    # Museum seam: the first activation entry becomes the kernel set; the
    # second entry is silently dropped.
    assert node.kernel_refs == [contract.kernel_activation[0]]
    assert node.kernel_refs != list(contract.kernel_activation)
