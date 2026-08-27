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

import pytest

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
    """PHASE-05 conversion: the prompt_compiler substitution museum seam is gone.

    A structured step's declared kernel_refs survive verbatim — the graph
    never substitutes a kernel the contract did not declare.
    """
    steps = [
        {
            "step_id": "step.P2_TASK_ROUTING",
            "phase": "P2_TASK_ROUTING",
            "kernel_refs": ["runtime/kernels/task/developer_core_kernel.yaml"],
            "obligation_refs": ["OBL.REALIZATION"],
            "input_refs": [],
            "output_refs": ["KERNEL_ACTIVATION_PLAN.yaml"],
            "entry_gates": [],
            "exit_gates": [],
            "evidence_requirements": ["realization evidence"],
            "failure_routes": ["BLOCKED", "ABORTED"],
        }
    ]
    contract = ExecutionContract.from_mapping(make_execution(execution_steps=steps))
    graph = derive_execution_graph(contract)
    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    assert node.id == "step.P2_TASK_ROUTING"
    assert node.kernel_refs == ["runtime/kernels/task/developer_core_kernel.yaml"]
    assert "prompt_compiler_kernel" not in node.kernel_refs


def test_a0003_unknown_step_collapses_to_first_kernel_activation(make_execution) -> None:  # type: ignore[no-untyped-def]
    """PHASE-05 conversion: the unknown-step first-kernel fallback is gone.

    There is no prose execution-sequence decoding left: a contract without
    structured steps cannot derive a graph at all.
    """
    contract = ExecutionContract.from_mapping(
        make_execution(execution_sequence=["a completely novel step nobody has heard of"])
    )
    with pytest.raises(Exception, match="execution_steps"):
        derive_execution_graph(contract)
