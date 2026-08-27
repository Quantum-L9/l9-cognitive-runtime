"""Live compilation spine for the L9 Cognitive Runtime.

Exactly one authoritative composition root exists for fresh missions
(INV-001): CompileRequest -> ObjectiveDeriver -> IntentContract ->
ActivationPlanner -> KernelResolver -> ExecutionContractCompiler ->
ValidationContractCompiler -> HandoffContractCompiler ->
ExecutionGraphCompiler -> RuntimeBundle.

Static FINAL_EXECUTION_CONTRACT.yaml / VALIDATION_CONTRACT.yaml /
HANDOFF_CONTRACT.yaml files in a pack are museum artifacts (INV-009) and are
never loaded as fresh-mission truth.
"""

from l9_cognitive_runtime.compiler.activation import ActivationPlan, ActivationPlanner
from l9_cognitive_runtime.compiler.execution import ExecutionContractCompiler
from l9_cognitive_runtime.compiler.handoff import HandoffContractCompiler
from l9_cognitive_runtime.compiler.kernels import KernelBinding, KernelResolver
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.pipeline import CompilePipeline
from l9_cognitive_runtime.compiler.validation import ValidationContractCompiler

__all__ = [
    "ActivationPlan",
    "ActivationPlanner",
    "CompilePipeline",
    "ExecutionContractCompiler",
    "HandoffContractCompiler",
    "KernelBinding",
    "KernelResolver",
    "ObjectiveDeriver",
    "ValidationContractCompiler",
]
