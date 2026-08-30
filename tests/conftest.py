"""Shared test fixtures.

``build_pack`` / ``valid_pack`` construct a MANIFEST.json-verified pack from
the repository's real validation/handoff/graph files plus a self-consistent,
constructed execution contract whose activated kernels exist as verified files
in the pack. The fail-closed service requires a verified pack, non-null
provenance, required contract documents (no synthesis), a non-empty activation
plan, and known kernels — so tests cannot depend on the mutable repository
root, whose committed manifest no longer matches the tree edited by the stack.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from l9_cognitive_runtime.compiler.task_context import (
    ContextDiscoveryCompiler,
    resolve_snapshot,
)
from l9_cognitive_runtime.compiler.task_scope import TaskScopeCompiler
from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.context import (
    AuthorityLevel,
    ContextScopeMode,
    ContextSnapshot,
    ContextSourceRef,
    DiscoveryContext,
    GovernedConstraint,
)

ROOT = Path(__file__).resolve().parents[1]

# Files copied verbatim from the repository pack (they validate against their models).
COPIED_FILES = (
    "VALIDATION_CONTRACT.yaml",
    "HANDOFF_CONTRACT.yaml",
    "EXECUTION_GRAPH.json",
)

# Kernel files the constructed execution contract activates; created in every pack.
DEFAULT_KERNELS = ("kernels/repo_auditor.yaml", "kernels/flawless_victory.yaml")

MINIMAL_EXECUTION: dict[str, Any] = {
    "contract_id": "FINAL_EXECUTION_CONTRACT",
    "contract_type": "universal_execution_contract",
    "source_activation_plan": "kernels/plan.yaml",
    "terminal_doctrine": "kernels/flawless_victory.yaml",
    "objective": "compile the representative pack",
    "authority_order": ["user task", "kernel activation plan", "Unknown"],
    "kernel_activation": list(DEFAULT_KERNELS),
    "execution_sequence": [
        "lock context",
        "run constitutional preflight",
        "execute terminal doctrine only after gates pass",
    ],
    "validation_requirements": ["pipeline order validated", "no fake validation"],
    "output_contract": ["execution_graph", "validation_evidence"],
    "adapter_targets": ["claude_code", "cursor"],
    "version": "1.0.0",
}


def write_manifest(pack: Path) -> None:
    """Write a MANIFEST.json whose digests match the pack's content files."""
    files = []
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.json":
            data = path.read_bytes()
            files.append(
                {
                    "path": path.relative_to(pack).as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
    manifest = {"pack_name": "test-pack", "files": files}
    (pack / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")


def build_pack(
    pack: Path,
    *,
    execution: dict[str, Any] | None = None,
    execution_text: str | None = None,
    kernels: tuple[str, ...] = DEFAULT_KERNELS,
) -> Path:
    """Construct a verified pack.

    - ``execution`` overrides the execution-contract mapping (defaults to a
      valid minimal contract). Set it to ``None`` with ``omit_execution`` behavior
      by passing ``execution={}`` is NOT allowed; use ``execution_text``/omission.
    - ``execution_text`` writes raw text (for malformed-YAML tests).
    - Passing ``execution=None`` AND ``execution_text=None`` omits the execution
      file entirely (for missing-required tests).
    - The live compiler spine resolves routing rules, the pipeline definition,
      and activated kernels from the pack, so every pack carries the
      repository ``runtime/`` tree.
    """
    pack.mkdir(parents=True, exist_ok=True)
    for kernel in kernels:
        kpath = pack / kernel
        kpath.parent.mkdir(parents=True, exist_ok=True)
        kpath.write_text(f"kernel_id: {Path(kernel).stem}\n", encoding="utf-8")
    if execution_text is not None:
        (pack / "FINAL_EXECUTION_CONTRACT.yaml").write_text(execution_text, encoding="utf-8")
    elif execution is not None:
        (pack / "FINAL_EXECUTION_CONTRACT.yaml").write_text(
            yaml.safe_dump(execution), encoding="utf-8"
        )
    for name in COPIED_FILES:
        shutil.copyfile(ROOT / name, pack / name)
    runtime_src = ROOT / "runtime"
    if runtime_src.is_dir():
        for src in runtime_src.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(ROOT).as_posix()
            dst = pack / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    write_manifest(pack)
    return pack


def execution_mapping(**overrides: Any) -> dict[str, Any]:
    """Return a copy of the minimal execution contract with overrides applied."""
    mapping = copy.deepcopy(MINIMAL_EXECUTION)
    mapping.update(overrides)
    return mapping


@pytest.fixture
def valid_pack(tmp_path: Path) -> Path:
    return build_pack(tmp_path / "pack", execution=MINIMAL_EXECUTION)


@pytest.fixture
def pack_builder() -> Callable[..., Path]:
    """Return the ``build_pack`` factory for tests that need pack variants."""
    return build_pack


@pytest.fixture
def make_execution() -> Callable[..., dict[str, Any]]:
    """Return the ``execution_mapping`` factory for overriding the contract."""
    return execution_mapping


# ---------------------------------------------------------------------------
# Governed context helpers.
#
# Under INV-CTX-014 a raw ``source_context.context_signals`` hint cannot prove
# an external architecture fact — only a provenance-backed governed item can.
# These helpers build the governed equivalent of the old caller-hint signals.
# ---------------------------------------------------------------------------


def governed_signal_snapshot(*signals: str) -> ContextSnapshot:
    """A snapshot proving each named architecture signal as governed law."""
    return ContextSnapshot(
        architecture_constraints=[
            GovernedConstraint(
                item_id=f"constraint.{signal}",
                semantic_key=signal,
                authority_level=AuthorityLevel.GOVERNED_AUTHORITATIVE,
                source_ref=ContextSourceRef(
                    source_id=f"governance:{signal}",
                    source_kind="architecture_review",
                    locator=f"governance://architecture/{signal}",
                    immutable_coordinate=f"review-{signal}",
                ),
                scope_mode=ContextScopeMode.GLOBAL,
                constraint_id=signal,
                statement=f"{signal} is proven for this task scope",
                applies_because=["governed architecture review"],
            )
            for signal in signals
        ]
    )


def discovery_for(intent: IntentContract, snapshot: ContextSnapshot) -> DiscoveryContext:
    """Run the real bounded discovery projection for a direct planner call."""
    scope = TaskScopeCompiler().compile(intent)
    return ContextDiscoveryCompiler().compile(scope, snapshot, resolve_snapshot(snapshot))


@pytest.fixture
def governed_signals() -> Callable[..., ContextSnapshot]:
    """Factory for a governed snapshot proving named architecture signals."""
    return governed_signal_snapshot


@pytest.fixture
def governed_discovery() -> Callable[..., DiscoveryContext]:
    """Factory running the real discovery projection for a direct planner call."""
    return discovery_for
