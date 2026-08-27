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

from l9_cognitive_runtime.models import ExecutionContract
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

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
            str(tmp_path / "OUT.yaml"),
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
