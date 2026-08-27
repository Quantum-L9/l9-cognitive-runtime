"""PHASE-00/PHASE-01 baseline locks for GAR Phase 2 integration (L9CR.GAR.PHASE2.INTEGRATION.001).

Each test pins a museum seam so later phases can prove the seam is removed:

- A0001 (PHASE-00): semantically different missions shared static pack
  artifacts. Converted in PHASE-01: missions now derive independent IRs and a
  pack with no static FINAL_EXECUTION_CONTRACT.yaml still compiles.
- A0002: the task-and-architecture step substitutes ``prompt_compiler_kernel``.
  (Removed by PHASE-05.)
- A0003: an unknown execution-sequence step collapses to the first
  ``kernel_activation`` entry. (Removed by PHASE-05.)
"""

from __future__ import annotations

from pathlib import Path

from l9_cognitive_runtime.graph import derive_execution_graph
from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def test_a0001_different_missions_derive_independent_runtime_irs(  # type: ignore[no-untyped-def]
    tmp_path: Path, pack_builder
) -> None:
    """PHASE-01 conversion: the static-sharing museum seam is gone.

    Two semantically different missions compile to independently derived IRs,
    and a pack with no static FINAL_EXECUTION_CONTRACT.yaml at all still
    compiles — the static artifact has no fresh-mission authority.
    """
    pack = pack_builder(tmp_path / "pack", execution=None)
    service = CognitiveRuntimeService()
    audit = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=pack)
    )
    audit_and_fix = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=pack)
    )
    audit_digests = audit.digests()
    fix_digests = audit_and_fix.digests()
    # Live spine: the mission is material to the execution contract (objective);
    # no static artifact is shared. (PHASE-03 propagates obligations so the
    # remaining IRs diverge for materially different missions.)
    assert audit_digests["execution"] != fix_digests["execution"]


def test_a0002_task_and_architecture_step_substitutes_prompt_compiler(make_execution) -> None:  # type: ignore[no-untyped-def]
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


def test_a0003_unknown_step_collapses_to_first_kernel_activation(make_execution) -> None:  # type: ignore[no-untyped-def]
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
