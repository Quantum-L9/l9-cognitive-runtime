"""Repo-root composition helper for the legacy runtime/ CLI wrappers.

The production spine is ``CompilePipeline`` (pack-verified). The legacy
``runtime/`` scripts historically ran against the repository root without a
verified manifest; they now delegate to the same typed compilers through this
helper, so no second semantic compiler implementation remains reachable
(A0103/A0104).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from l9_cognitive_runtime.compiler.activation import ActivationPlan, ActivationPlanner
from l9_cognitive_runtime.compiler.execution import ExecutionContractCompiler
from l9_cognitive_runtime.compiler.handoff import HandoffContractCompiler
from l9_cognitive_runtime.compiler.kernels import KernelBinding, KernelResolver
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.validation import ValidationContractCompiler
from l9_cognitive_runtime.models import (
    ExecutionContract,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.parsing import load_yaml_file
from l9_cognitive_runtime.types import CompileRequest

RULES_REL = "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml"
PIPELINE_REL = "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"


@dataclass(frozen=True)
class CompiledContracts:
    intent: IntentContract
    plan: ActivationPlan
    kernels: list[KernelBinding]
    execution: ExecutionContract
    validation: ValidationContract
    handoff: HandoffContract


def compile_execution_from_plan(root: Path, plan: ActivationPlan) -> ExecutionContract:
    """Compile an execution contract from a typed activation plan (repo root)."""
    intent = ObjectiveDeriver().derive(CompileRequest(mission=plan.task_summary))
    kernels = KernelResolver().resolve(plan.active_kernels, root)
    pipeline = load_yaml_file(root / PIPELINE_REL)
    return ExecutionContractCompiler().compile(intent, plan, kernels, pipeline)


def compile_from_root(
    root: Path,
    mission: str,
    *,
    include_terminal: bool = False,
) -> CompiledContracts:
    """Compile the canonical contract set for a mission from a repo-root pack."""
    intent = ObjectiveDeriver().derive(CompileRequest(mission=mission))
    plan = ActivationPlanner().plan(
        intent,
        rules_path=root / RULES_REL,
        pipeline_path=root / PIPELINE_REL,
        include_terminal=include_terminal,
    )
    kernels = KernelResolver().resolve(plan.active_kernels, root)
    pipeline = load_yaml_file(root / PIPELINE_REL)
    execution = ExecutionContractCompiler().compile(intent, plan, kernels, pipeline)
    validation = ValidationContractCompiler().compile(intent, execution, plan)
    handoff = HandoffContractCompiler().compile(intent, execution, validation, plan)
    return CompiledContracts(
        intent=intent,
        plan=plan,
        kernels=kernels,
        execution=execution,
        validation=validation,
        handoff=handoff,
    )
