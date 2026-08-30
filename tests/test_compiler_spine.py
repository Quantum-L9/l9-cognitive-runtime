"""PHASE-01 gate evidence: exactly one live compilation spine.

Covers the single-spine gate of L9CR.GAR.PHASE2.INTEGRATION.001:

- static pack contracts are never loaded as fresh-mission truth;
- missing routing sources fail closed;
- equivalent inputs produce equivalent IRs across service surfaces;
- the legacy runtime/ wrappers delegate to the same typed compilers.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from l9_cognitive_runtime.compiler import CompilePipeline
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from tests.conftest import MINIMAL_EXECUTION, build_pack

ROOT = Path(__file__).resolve().parents[1]


def _manifest_without(pack: Path, *removed: str) -> None:
    files = json.loads((pack / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    files = [entry for entry in files if entry["path"] not in removed]
    (pack / "MANIFEST.json").write_text(
        json.dumps({"pack_name": "test-pack", "files": files}) + "\n", encoding="utf-8"
    )


def test_static_final_contract_has_no_fresh_authority(tmp_path: Path, pack_builder) -> None:  # type: ignore[no-untyped-def]
    """A pack with no static FINAL_EXECUTION_CONTRACT.yaml still compiles."""
    pack = pack_builder(tmp_path / "pack", execution=None)
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=pack)
    )
    assert bundle.execution.contract_id == "FINAL_EXECUTION_CONTRACT"
    assert bundle.execution.kernel_activation
    assert bundle.graph.nodes


def test_missing_routing_rules_fail_closed(tmp_path: Path, pack_builder) -> None:  # type: ignore[no-untyped-def]
    """Live compilation without routing rules in the pack fails closed."""
    pack = pack_builder(tmp_path / "pack")
    rules = pack / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml"
    rules.unlink()
    _manifest_without(pack, "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml")
    with pytest.raises(InvalidValueError):
        CognitiveRuntimeService().compile_runtime(
            CompileRequest(mission="Audit this repository.", pack_root=pack)
        )


def test_missing_pipeline_fail_closed(tmp_path: Path, pack_builder) -> None:  # type: ignore[no-untyped-def]
    """Live compilation without the pipeline definition fails closed."""
    pack = pack_builder(tmp_path / "pack")
    pipeline = pack / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml"
    pipeline.unlink()
    _manifest_without(pack, "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml")
    with pytest.raises(InvalidValueError):
        CognitiveRuntimeService().compile_runtime(
            CompileRequest(mission="Audit this repository.", pack_root=pack)
        )


def test_equivalent_inputs_produce_equivalent_irs(valid_pack: Path) -> None:
    """Same mission through the service twice yields identical digests."""
    service = CognitiveRuntimeService()
    first = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    second = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    assert first.digests() == second.digests()
    assert first.execution.sha256() == second.execution.sha256()
    assert first.graph.sha256() == second.graph.sha256()


def test_cli_and_service_share_the_spine(tmp_path: Path, valid_pack: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI output digests match a direct service compile (one spine)."""
    from l9_cognitive_runtime.cli import main as cli_main

    assert cli_main(["--mission", "Audit this repository.", "--pack-root", str(valid_pack)]) == 0
    out = json.loads(capsys.readouterr().out)
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    assert out["digests"] == bundle.digests()


def test_legacy_execution_compiler_wraps_same_compiler(tmp_path: Path) -> None:
    """runtime/contract_compiler/compile_execution_contract.py delegates to the
    typed ExecutionContractCompiler and produces identical semantics."""
    plan_path = tmp_path / "KERNEL_ACTIVATION_PLAN.yaml"
    from l9_cognitive_runtime.compiler import ActivationPlanner, ObjectiveDeriver
    from l9_cognitive_runtime.compiler.context import compile_execution_from_plan
    from l9_cognitive_runtime.compiler.kernels import KernelResolver
    from l9_cognitive_runtime.types import CompileRequest

    intent = ObjectiveDeriver().derive(CompileRequest(mission="compile a kernel contract"))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=ROOT / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=ROOT / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
    )
    plan_path.write_text(yaml.safe_dump(plan.to_dict(), sort_keys=False), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "contract_compiler" / "compile_execution_contract.py"),
            "--root",
            str(ROOT),
            "--activation-plan",
            str(plan_path),
            "--out",
            "OUT.yaml",
            "--allow-write-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    wrapped = ExecutionContract.from_mapping(
        yaml.safe_load((tmp_path / "OUT.yaml").read_text(encoding="utf-8"))
    )
    direct = compile_execution_from_plan(ROOT, plan)
    assert wrapped.to_canonical_dict() == direct.to_canonical_dict()
    assert wrapped.kernel_activation == [
        binding.source_ref for binding in KernelResolver().resolve(plan.active_kernels, ROOT)
    ]


def test_graph_cli_requires_a_contract_with_structured_steps(tmp_path: Path) -> None:
    """A0501: the graph CLI has no default source contract.

    The static FINAL_EXECUTION_CONTRACT.yaml is an inert museum artifact with
    no execution_steps, so it can never derive a graph; the CLI must demand an
    explicit contract rather than default to guaranteed failure. Given a
    contract from the live spine it derives the graph.
    """
    from l9_cognitive_runtime.compiler import ActivationPlanner, ObjectiveDeriver
    from l9_cognitive_runtime.compiler.context import compile_execution_from_plan
    from l9_cognitive_runtime.types import CompileRequest

    script = ROOT / "runtime" / "execution_graph" / "build_execution_graph.py"

    missing = subprocess.run(
        [sys.executable, str(script), "--root", str(ROOT)], capture_output=True, text=True
    )
    assert missing.returncode != 0
    assert "--source-contract" in missing.stderr

    intent = ObjectiveDeriver().derive(CompileRequest(mission="compile a kernel contract"))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=ROOT / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml",
        pipeline_path=ROOT / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml",
    )
    contract = compile_execution_from_plan(ROOT, plan).to_canonical_dict()
    assert contract["execution_steps"], "live spine must emit structured steps"
    (tmp_path / "LIVE.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    built = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(tmp_path),
            "--source-contract",
            "LIVE.yaml",
            "--output",
            "GRAPH.json",
            "--allow-write-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    graph = json.loads((tmp_path / "GRAPH.json").read_text(encoding="utf-8"))
    assert len(graph["nodes"]) == len(contract["execution_steps"])


# --------------------------------------------------------------------------
# A003 / A008: the context stages live on the same one spine.
# --------------------------------------------------------------------------


def test_context_stages_run_on_the_same_compile_pipeline(tmp_path: Path) -> None:
    """Every context artifact comes from one ``CompilePipeline.compile`` call."""
    pack = build_pack(tmp_path / "pack", execution=MINIMAL_EXECUTION)
    request = CompileRequest(mission="single spine context compile", pack_root=pack)
    bundle = CompilePipeline().compile(request, PackLoader().load(pack))

    # The context exists, is closed, and is bound to this compile's kernels.
    assert bundle.task_context.provenance.task_scope_digest
    assert bundle.task_context.selected_kernels == [
        binding.to_dict()
        for binding in KernelResolver().resolve(list(bundle.execution.kernel_activation), pack)
    ]
    # The digest reached both downstream carriers from that one pass.
    context_digest = bundle.digests()["context"]
    assert bundle.packet["compiled_task_context_digest"] == context_digest
    assert (bundle.execution.metadata or {})["context_digest"] == context_digest


def test_no_second_semantic_path_produces_a_context(tmp_path: Path) -> None:
    """The service adds nothing: it is a facade over the same pipeline."""
    pack = build_pack(tmp_path / "pack", execution=MINIMAL_EXECUTION)
    request = CompileRequest(mission="facade equivalence", pack_root=pack)
    direct = CompilePipeline().compile(request, PackLoader().load(pack))
    through_service = CognitiveRuntimeService().compile_runtime(request)
    assert direct.task_context.to_canonical_json() == (
        through_service.task_context.to_canonical_json()
    )
    assert direct.semantic_digest == through_service.semantic_digest
