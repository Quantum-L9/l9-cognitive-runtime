"""Live compilation spine for the L9 Cognitive Runtime.

Exactly one authoritative composition root exists for fresh missions
(INV-001, INV-CTX-002): CompileRequest + ContextSnapshot -> ObjectiveDeriver ->
TaskScopeCompiler -> ContextDiscoveryCompiler -> ActivationPlanner ->
KernelResolver -> ContextRequirementPlanner -> ContextCompiler ->
ContextClosureValidator -> ObligationDeriver -> ExecutionContractCompiler ->
ValidationContractCompiler -> HandoffContractCompiler ->
ExecutionGraphCompiler -> ExecutionPacket -> validate_packet ->
BundleSemanticValidator -> RuntimeBundle.

Static FINAL_EXECUTION_CONTRACT.yaml / VALIDATION_CONTRACT.yaml /
HANDOFF_CONTRACT.yaml files in a pack are museum artifacts (INV-009) and are
never loaded as fresh-mission truth.
"""

from l9_cognitive_runtime.compiler.activation import ActivationPlan, ActivationPlanner
from l9_cognitive_runtime.compiler.context_closure import (
    ContextClosureReport,
    ContextClosureValidator,
)
from l9_cognitive_runtime.compiler.context_requirements import ContextRequirementPlanner
from l9_cognitive_runtime.compiler.execution import ExecutionContractCompiler
from l9_cognitive_runtime.compiler.handoff import HandoffContractCompiler
from l9_cognitive_runtime.compiler.kernels import (
    KernelBinding,
    KernelContextNeed,
    KernelResolver,
)
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.pipeline import CompilePipeline, RootCompilation
from l9_cognitive_runtime.compiler.task_context import (
    ContextCompiler,
    ContextDiscoveryCompiler,
    SnapshotResolution,
    preflight_snapshot,
    resolve_snapshot,
)
from l9_cognitive_runtime.compiler.task_scope import TaskScopeCompiler
from l9_cognitive_runtime.compiler.validation import ValidationContractCompiler

__all__ = [
    "ActivationPlan",
    "ActivationPlanner",
    "CompilePipeline",
    "ContextClosureReport",
    "ContextClosureValidator",
    "ContextCompiler",
    "ContextDiscoveryCompiler",
    "ContextRequirementPlanner",
    "ExecutionContractCompiler",
    "HandoffContractCompiler",
    "KernelBinding",
    "KernelContextNeed",
    "KernelResolver",
    "ObjectiveDeriver",
    "RootCompilation",
    "SnapshotResolution",
    "TaskScopeCompiler",
    "ValidationContractCompiler",
    "preflight_snapshot",
    "resolve_snapshot",
]
