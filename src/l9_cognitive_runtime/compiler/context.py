"""Repo-root compatibility surface for the legacy ``runtime/`` CLI wrappers.

These functions exist so the ``runtime/contract_compiler/*.py`` scripts keep
their invocation shapes. They own **no** semantics: every call delegates to
``CompilePipeline.compile_from_root``, the pipeline-owned compatibility entry
that joins the one canonical internal path (INV-CTX-002).

That distinction is the whole point of this module's current shape. It used to
sequence ``ObjectiveDeriver`` -> ``ActivationPlanner`` -> ``KernelResolver`` ->
``ObligationDeriver`` -> contract compilers itself, which made it a second
semantic composition owner: a chain that produced IRs while bypassing context
closure, packet validation, and runtime semantic liveness entirely. Delegating
removes that bypass — the wrappers now get artifacts that survived the full
spine, not a shorter one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.pipeline import CompilePipeline
from l9_cognitive_runtime.models import (
    ExecutionContract,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.models.context import CompiledTaskContext


@dataclass(frozen=True)
class CompiledContracts:
    intent: IntentContract
    plan: ActivationPlan
    kernels: list[KernelBinding]
    execution: ExecutionContract
    validation: ValidationContract
    handoff: HandoffContract
    task_context: CompiledTaskContext


def compile_execution_from_plan(root: Path, plan: ActivationPlan) -> ExecutionContract:
    """Compile an execution contract from a typed activation plan (repo root).

    The supplied plan replaces routing and nothing else: the compile still runs
    the full spine, so the returned contract is the same artifact the canonical
    path produces for that plan.
    """
    result = CompilePipeline().compile_from_root(
        root,
        plan.task_summary,
        activation_plan=plan,
    )
    return result.bundle.execution


def compile_from_root(
    root: Path,
    mission: str,
    *,
    include_terminal: bool = False,
) -> CompiledContracts:
    """Compile the canonical contract set for a mission from a repo-root pack."""
    result = CompilePipeline().compile_from_root(
        root,
        mission,
        include_terminal=include_terminal,
    )
    bundle = result.bundle
    return CompiledContracts(
        intent=bundle.intent,
        plan=result.plan,
        kernels=result.kernels,
        execution=bundle.execution,
        validation=bundle.validation,
        handoff=bundle.handoff,
        task_context=bundle.task_context,
    )


__all__ = [
    "CompiledContracts",
    "compile_execution_from_plan",
    "compile_from_root",
]
