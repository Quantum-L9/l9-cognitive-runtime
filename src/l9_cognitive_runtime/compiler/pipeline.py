"""The single live compilation spine (INV-001).

Exactly one authoritative path composes fresh missions into a runtime bundle:

CompileRequest -> ObjectiveDeriver -> IntentContract -> ActivationPlanner ->
KernelResolver -> ObligationDeriver -> ExecutionContractCompiler ->
ValidationContractCompiler -> HandoffContractCompiler ->
ExecutionGraphCompiler -> RuntimeBundle.

All semantic inputs (routing rules, pipeline definition, kernels) are
resolved from the verified pack and fail closed when absent. Obligations are
derived once and conserved through every downstream IR (INV-003).
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.execution import ExecutionContractCompiler
from l9_cognitive_runtime.compiler.handoff import HandoffContractCompiler
from l9_cognitive_runtime.compiler.kernels import KernelResolver
from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
from l9_cognitive_runtime.compiler.obligations import (
    ObligationDeriver,
    conserve,
    conserve_ids,
    owner_registry,
    required_pending_ids,
    validate_obligations,
)
from l9_cognitive_runtime.compiler.validation import ValidationContractCompiler
from l9_cognitive_runtime.graph import derive_execution_graph
from l9_cognitive_runtime.models.errors import InvalidValueError
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

        # INV-003: derive obligations once, then conserve them through every IR.
        obligations = ObligationDeriver().derive(intent, plan, kernels)
        validate_obligations(obligations, owner_registry(plan, kernels), stage="intent")
        intent.obligations = obligations

        execution = ExecutionContractCompiler().compile(
            intent, plan, kernels, pipeline, obligations
        )
        conserve(intent.obligations, execution.obligations, stage="intent->execution")
        validation = ValidationContractCompiler().compile(intent, execution, plan)
        conserve_ids(
            execution.obligations,
            [property.obligation_ref for property in validation.validation_properties],
            stage="execution->validation",
        )
        handoff = HandoffContractCompiler().compile(intent, execution, validation, plan)
        conserve(execution.obligations, handoff.obligations, stage="execution->handoff")
        graph = derive_execution_graph(execution)
        required_ids = required_pending_ids(execution.obligations)
        if graph.obligation_refs != required_ids:
            raise InvalidValueError(
                "graph obligation_refs diverged from required pending obligations",
                path="execution->graph",
                details={"expected": required_ids, "got": graph.obligation_refs},
            )
        return RuntimeBundle(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            provenance=pack.provenance,
        )
