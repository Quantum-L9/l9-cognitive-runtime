"""The single live compilation spine (INV-001).

Exactly one authoritative path composes fresh missions into a runtime bundle:

CompileRequest -> ObjectiveDeriver -> IntentContract -> ActivationPlanner ->
KernelResolver -> ObligationDeriver -> ExecutionContractCompiler ->
ValidationContractCompiler -> HandoffContractCompiler ->
ExecutionGraphCompiler -> BundleSemanticValidator -> RuntimeBundle.

All semantic inputs (routing rules, pipeline definition, kernels) are
resolved from the verified pack and fail closed when absent. Obligations are
derived once and conserved through every downstream IR (INV-003).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from l9_cognitive_runtime.compiler.activation import ActivationPlanner
from l9_cognitive_runtime.compiler.execution import ExecutionContractCompiler
from l9_cognitive_runtime.compiler.handoff import HandoffContractCompiler
from l9_cognitive_runtime.compiler.kernels import KernelBinding, KernelResolver
from l9_cognitive_runtime.compiler.liveness import validate_runtime_semantic_liveness
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
from l9_cognitive_runtime.models import (
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.models.canonical import canonical_json, sha256_digest
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import RuntimePack
from l9_cognitive_runtime.parsing import load_yaml_file
from l9_cognitive_runtime.types import CompileRequest, RuntimeBundle

RULES_REL = "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml"
PIPELINE_REL = "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            sorted({property.obligation_ref for property in validation.validation_properties}),
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
        # BundleSemanticValidator: compile-time semantic liveness, fail closed.
        validate_runtime_semantic_liveness(
            intent=intent,
            plan=plan,
            kernels=kernels,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
        )
        semantic_digest = self._semantic_digest(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            kernels=kernels,
            rules_path=rules_path,
            pipeline_path=pipeline_path,
        )
        return RuntimeBundle(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            provenance=pack.provenance,
            semantic_digest=semantic_digest,
        )

    @staticmethod
    def _semantic_digest(
        *,
        intent: IntentContract,
        execution: ExecutionContract,
        validation: ValidationContract,
        handoff: HandoffContract,
        graph: ExecutionGraph,
        kernels: list[KernelBinding],
        rules_path: Path,
        pipeline_path: Path,
    ) -> str:
        """Bundle semantic digest over every provenance-contract input.

        Active kernel digests participate (canonical order); inactive kernel
        content does not. Compiler IR digests stand in for compiler semantics.
        """
        payload = {
            "intent_digest": intent.sha256(),
            "execution_digest": execution.sha256(),
            "validation_digest": validation.sha256(),
            "handoff_digest": handoff.sha256(),
            "graph_digest": graph.sha256(),
            "obligation_set_digest": sha256_digest(
                [obligation.obligation_id for obligation in execution.obligations]
            ),
            "active_kernel_digests": {
                binding.source_ref: binding.source_digest for binding in kernels
            },
            "routing_rules_digest": _file_sha256(rules_path),
            "pipeline_digest": _file_sha256(pipeline_path),
        }
        return sha256_digest(canonical_json(payload))

