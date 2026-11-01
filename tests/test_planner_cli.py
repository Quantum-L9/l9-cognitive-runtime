"""The activation planner CLI emits the plan it routed, blocked or not (RU-15).

``plan_activation.py`` exits 1 when the plan carries blockers. That branch is
only reachable if the CLI receives the plan before execution compilation —
which rejects blocked plans — so the CLI projects the PLAN view of the shared
semantic prefix rather than a full compile.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from l9_cognitive_runtime.compiler import CompilePipeline

ROOT = Path(__file__).resolve().parents[1]
PLANNER = Path("runtime") / "kernel_pipeline" / "planner" / "plan_activation.py"
RULES = Path("runtime") / "kernel_pipeline" / "planner" / "TASK_ROUTING_RULES.yaml"


def _run_planner(root: Path, task: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run(
        [sys.executable, str(root / PLANNER), task],
        capture_output=True,
        text=True,
        env=env,
    )


def test_blocked_plan_is_printed_and_exits_one(tmp_path: Path) -> None:
    """RG-015a: rules that produce a blocker still yield the plan, with exit 1.

    The kernel-compilation route loses its constitutional preflight phase, so
    an L9 kernel mission is planned with the "without constitutional
    preflight" blocker.
    """
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "runtime", root / "runtime")
    rules = yaml.safe_load((root / RULES).read_text(encoding="utf-8"))
    route = rules["task_routes"]["prompt_or_kernel_compilation"]
    route["phases"] = [phase for phase in route["phases"] if phase != "P1_CONSTITUTIONAL_PREFLIGHT"]
    (root / RULES).write_text(yaml.safe_dump(rules, sort_keys=False), encoding="utf-8")

    proc = _run_planner(root, "compile a kernel contract")

    # Exit 1 alone proves nothing: an uncaught compile error also exits 1.
    assert proc.stdout.strip(), proc.stderr
    assert proc.returncode == 1, proc.stdout + proc.stderr
    plan = yaml.safe_load(proc.stdout)
    assert plan["matched_route"] == "prompt_or_kernel_compilation"
    assert plan["blockers"] == ["L9-related task without constitutional preflight."]
    assert "P1_CONSTITUTIONAL_PREFLIGHT" not in plan["phase_sequence"]


def test_unblocked_plan_is_the_compiled_plan() -> None:
    """An unblocked plan is unchanged: it is the plan the full spine compiles."""
    task = "clean and dedupe this L9 kernel pack"
    proc = _run_planner(ROOT, task)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    compiled = CompilePipeline().compile_from_root(ROOT, task)
    assert yaml.safe_load(proc.stdout) == compiled.plan.to_dict()
