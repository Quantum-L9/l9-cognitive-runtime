"""The single live compilation spine (INV-001).

Exactly one authoritative path composes fresh missions into a runtime bundle:

CompileRequest -> ObjectiveDeriver -> IntentContract -> ActivationPlanner ->
KernelResolver -> ExecutionContractCompiler -> ValidationContractCompiler ->
HandoffContractCompiler -> ExecutionGraphCompiler -> RuntimeBundle.

All semantic inputs (routing rules, pipeline definition, kernels) are
resolved from the verified pack and fail closed when absent.
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.execution import ExecutionContractCompiler
from l9_cognitive_runtime.compiler.handoff import HandoffContractCompiler
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.validation import ValidationContractCompiler
from l9_cognitive_runtime.graph import derive_execution_graph
from l9_cognitive_runtime.pack import RuntimePack
from l9_cognitive_runtime.parsing import load_yaml_file
from l9_cognitive_runtime.types import CompileRequest, RuntimeBundle

RULES_REL = "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml"
PIPELINE_REL = "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"


class CompilePipeline:
    """Compose the live compiler spine over a verified pack."""

    def compile(self, request: CompileRequest, pack: RuntimePack) -> RuntimeBundle:
        intent = ObjectiveDeriver().derive(request)
        # pack.resolve fails closed when the routing sources are absent.
        rules_path = pack.resolve(RULES_REL)
        pipeline_path = pack.resolve(PIPELINE_REL)
        plan = ActivationPlanner().plan(
            intent,
            rules_path=rules_path,
            pipeline_path=pipeline_path,
        )
        kernels = KernelResolver().resolve(plan.active_kernels, pack.provenance.root)
        pipeline = load_yaml_file(pipeline_path)
        execution = ExecutionContractCompiler().compile(intent, plan, kernels, pipeline)
        validation = ValidationContractCompiler().compile(intent, execution, plan)
        handoff = HandoffContractCompiler().compile(intent, execution, validation, plan)
        graph = derive_execution_graph(execution)
        return RuntimeBundle(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            provenance=pack.provenance,
        )
