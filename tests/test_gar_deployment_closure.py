"""PHASE-08 gate evidence: deployment semantic closure (INV-011, A0801-A0803).

Gate coverage:

- dynamic_routes_compile_from_sealed_pack;
- missing_required_kernel_fails_pack_validation;
- missing_routing_source_fails_pack_validation;
- no_repository_relative_hidden_dependency;
- identical_pack_and_intent_produce_deterministic_bundle;
- A0803: installed wheel + sealed pack + empty working directory compiles
  without a repository checkout.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.deployment import (
    build_deployment_pack,
    validate_deployment_closure,
)
from l9_cognitive_runtime.models.errors import ModelValidationError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def _sealed_pack(tmp_path: Path) -> Path:
    return build_deployment_pack(ROOT, tmp_path / "pack", source_revision=REVISION)


def test_dynamic_routes_compile_from_sealed_pack(tmp_path: Path) -> None:
    pack = _sealed_pack(tmp_path)
    closure = PackLoader().load(pack).manifest["semantic_closure"]
    assert closure["routes_compiled"]
    assert closure["count"] >= 7
    # The sealed pack carries every dynamically selectable kernel and the
    # routing/pipeline sources — no static activation preselection (A0801).
    for rel in (
        "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml",
        "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml",
        "runtime/kernels/architecture/global_architect_kernel.yaml",
        "runtime/kernels/task/developer_core_kernel.yaml",
    ):
        assert (pack / rel).is_file(), rel


def test_identical_pack_and_intent_produce_deterministic_bundle(tmp_path: Path) -> None:
    pack = _sealed_pack(tmp_path)
    service = CognitiveRuntimeService()
    first = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=pack)
    )
    second = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=pack)
    )
    assert first.digests() == second.digests()
    assert first.packet == second.packet


def test_missing_required_kernel_fails_pack_validation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv", "dist", "__pycache__")
    )
    missing = source / "runtime" / "kernels" / "task" / "prompt_compiler_kernel.yaml"
    missing.unlink()
    with pytest.raises(ModelValidationError):
        build_deployment_pack(source, tmp_path / "pack", source_revision=REVISION)


def test_missing_routing_source_fails_pack_validation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        ROOT, source, ignore=shutil.ignore_patterns(".git", ".venv", "dist", "__pycache__")
    )
    rules = source / "runtime" / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml"
    rules.unlink()
    with pytest.raises(ModelValidationError):
        build_deployment_pack(source, tmp_path / "pack", source_revision=REVISION)


def test_no_repository_relative_hidden_dependency(tmp_path: Path) -> None:
    pack = _sealed_pack(tmp_path)
    manifest = PackLoader().load(pack).manifest
    for entry in manifest["files"]:
        source_path = Path(entry["source_path"])
        assert not source_path.is_absolute()
        assert ".." not in source_path.parts
    # Closure proof re-runs cleanly against the sealed pack.
    report = validate_deployment_closure(pack)
    assert report["count"] >= 7


def test_isolated_wheel_and_sealed_pack_compile(tmp_path: Path) -> None:
    """A0803: built wheel + sealed pack + arbitrary empty cwd compiles a
    mission-derived runtime without a repository checkout."""
    import venv

    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    wheel = next(wheel_dir.glob("*.whl"))

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    venv_python = venv_dir / "bin" / "python"
    proc = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", str(wheel)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    pack = _sealed_pack(tmp_path / "sealed")
    workdir = tmp_path / "arbitrary_empty_working_directory"
    workdir.mkdir()
    script = (
        "import json, sys\n"
        "from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest\n"
        f"service = CognitiveRuntimeService()\n"
        "bundle = service.compile_runtime(\n"
        "    CompileRequest(mission='Audit this repository.', "
        f"pack_root={str(pack)!r})\n"
        ")\n"
        "print(json.dumps({'digests': bundle.digests(), 'nodes': len(bundle.graph.nodes)}))\n"
    )
    proc = subprocess.run(
        [str(venv_python), "-c", script],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload: dict[str, Any] = json.loads(proc.stdout)
    assert payload["digests"]["semantic"]
    assert payload["nodes"] >= 3
