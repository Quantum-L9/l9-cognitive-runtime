"""Live execution-contract compilation.

The execution contract is compiled from the canonical intent, the typed
activation plan, and the resolved kernel bindings. No static
``FINAL_EXECUTION_CONTRACT.yaml`` is ever loaded as fresh-mission truth
(INV-009): the file may exist only as a generated example or golden fixture.
"""

from __future__ import annotations

from typing import Any

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.models import ExecutionContract, IntentContract, Obligation
from l9_cognitive_runtime.models.context import CompiledTaskContext
from l9_cognitive_runtime.models.errors import InvalidValueError

# Canonical phase -> prose-step projection. P2 and P3 share one step: the
# graph compiler collapses duplicate logical steps into one node.
PHASE_STEP_MAP: dict[str, str] = {
    "P0_UNPACK": "lock context",
    "P1_CONSTITUTIONAL_PREFLIGHT": "run constitutional preflight",
    "P2_TASK_ROUTING": "apply selected task and architecture kernels",
    "P3_ARCHITECTURE_DECISION": "apply selected task and architecture kernels",
    "P4_ALIGNMENT_AND_STUB_GATE": "run alignment and stub gate",
    "P5_RECURSIVE_IMPROVEMENT": "run recursive improvement",
    "P6_LEVERAGE_COMPRESSION": "run leverage compression",
    "P7_FLAWLESS_VICTORY": "execute terminal doctrine only after gates pass",
}

# The compiler's own authority order. Preserved verbatim for backward
# compatibility and used only when governed context proves nothing more
# specific — in which case the compiled context labels its source
# ``compiler_default`` (INV-CTX-022). Caller hints never define this order.
AUTHORITY_ORDER = [
    "user task",
    "kernel activation plan",
    "repo files",
    "runtime pipeline contracts",
    "tests and validation evidence",
    "Unknown",
]

VALIDATION_REQUIREMENTS = [
    "pipeline order validated",
    "kernel roles unique",
    "no duplicate active kernels",
    "phase outputs satisfied or blocked with reason",
    "adapter render preserves canonical contract",
    "no fake validation",
]

STOP_CONDITIONS = [
    "activation plan missing or invalid",
    "required kernel unavailable",
    "terminal doctrine requested before gates pass",
    "validation cannot be run honestly",
    "scope conflict requires operator decision",
]

OUTPUT_CONTRACT = [
    "summary",
    "files_changed_or_artifacts_created",
    "validation_results",
    "remaining_unknowns",
    "merge_or_execution_readiness",
    "minimum_safe_next_action",
    "convergence_block",
]

ADAPTER_TARGETS = ["claude_code", "cursor", "codex", "chatgpt", "human_operator"]

ACTIVATION_PLAN_SOURCE = "runtime/kernel_pipeline/planner/KERNEL_ACTIVATION_PLAN.yaml"


class ExecutionContractCompiler:
    """Compile the live execution contract from intent + plan + kernels."""

    def compile(
        self,
        intent: IntentContract,
        plan: ActivationPlan,
        kernels: list[KernelBinding],
        pipeline: dict[str, Any],
        obligations: list[Obligation] | None = None,
        task_context: CompiledTaskContext | None = None,
        context_digest: str | None = None,
    ) -> ExecutionContract:
        if plan.blockers:
            raise InvalidValueError(
                "activation plan has blockers",
                path="activation_plan",
                details={"blockers": plan.blockers},
            )
        terminal_doctrine = pipeline.get("terminal_contract")
        if not isinstance(terminal_doctrine, str) or not terminal_doctrine.strip():
            raise InvalidValueError(
                "pipeline terminal_contract missing",
                path="runtime/kernel_pipeline/KERNEL_PIPELINE.yaml",
            )
        pipeline_id = pipeline.get("pipeline_id")
        if not isinstance(pipeline_id, str) or not pipeline_id.strip():
            raise InvalidValueError(
                "pipeline pipeline_id missing",
                path="runtime/kernel_pipeline/KERNEL_PIPELINE.yaml",
            )

        # Phase->kernel projection feeds both the metadata and the structured
        # steps (GAR appears in the graph by construction).
        phase_kernels: dict[str, list[str]] = {}
        for binding in kernels:
            for phase_id in plan.phase_sequence:
                phase = next(
                    (
                        item
                        for item in pipeline.get("phase_order", [])
                        if item.get("id") == phase_id
                    ),
                    None,
                )
                if phase and binding.source_ref in phase.get("primary_kernels", []):
                    phase_kernels.setdefault(phase_id, []).append(binding.source_ref)

        sequence: list[str] = []
        for phase_id in plan.phase_sequence:
            step = PHASE_STEP_MAP.get(phase_id)
            if step is None:
                raise InvalidValueError(
                    "phase has no canonical execution step",
                    path="phase_sequence",
                    details={"phase_id": phase_id},
                )
            sequence.append(step)

        # Structured steps (INV-006): the mechanical source for the graph.
        obligations = obligations or []
        obligations_by_id = {obligation.obligation_id: obligation for obligation in obligations}
        phase_by_id = {phase["id"]: phase for phase in pipeline.get("phase_order", [])}
        validation_phase = (
            "P4_ALIGNMENT_AND_STUB_GATE"
            if "P4_ALIGNMENT_AND_STUB_GATE" in plan.phase_sequence
            else "P2_TASK_ROUTING"
        )
        terminal_target = (
            "P7_FLAWLESS_VICTORY"
            if "P7_FLAWLESS_VICTORY" in plan.phase_sequence
            else plan.phase_sequence[-1]
        )
        kind_phase: dict[str, str] = {
            "AUTHORITY": "P1_CONSTITUTIONAL_PREFLIGHT",
            "REALIZATION": "P2_TASK_ROUTING",
            "ARCHITECTURE": "P3_ARCHITECTURE_DECISION",
            "EPISTEMIC": "P0_UNPACK",
            "VALIDATION": validation_phase,
            "DELIVERY": terminal_target,
            "CONVERGENCE": terminal_target,
        }

        # INV-CTX-022: a governed effective order supersedes the compiler
        # default when the compiled context proved one. The compiled context
        # records which source won; here we only consume the result.
        authority_order = (
            list(task_context.authority.effective_order)
            if task_context is not None and task_context.authority.effective_order
            else list(AUTHORITY_ORDER)
        )

        execution_steps: list[dict[str, Any]] = []
        previous_outputs: list[str] = []
        for phase_id in plan.phase_sequence:
            phase = phase_by_id.get(phase_id, {})
            kernels_in_step = list(phase_kernels.get(phase_id, []))
            gar_outputs: list[str] = []
            for binding in kernels:
                if binding.source_ref in kernels_in_step:
                    gar_outputs.extend(output.output_id for output in binding.outputs)
            required_outputs = list(phase.get("required_outputs", []))
            outputs = required_outputs + [o for o in gar_outputs if o not in required_outputs]
            obligation_ids = [
                obligation.obligation_id
                for obligation in obligations
                if kind_phase.get(obligation.kind.value) == phase_id
            ]
            evidence: list[str] = []
            for obligation_id in obligation_ids:
                obligation = obligations_by_id.get(obligation_id)
                if obligation is not None:
                    evidence.extend(obligation.evidence_requirements)
            exit_gates = [str(phase["exit_gate"])] if phase.get("exit_gate") else []
            failure_routes = (
                ["ABORTED"] if phase_id == "P7_FLAWLESS_VICTORY" else ["BLOCKED", "ABORTED"]
            )
            execution_steps.append(
                {
                    "step_id": f"step.{phase_id}",
                    "phase": phase_id,
                    "kernel_refs": kernels_in_step,
                    "obligation_refs": obligation_ids,
                    "input_refs": list(previous_outputs),
                    "output_refs": outputs,
                    "entry_gates": [],
                    "exit_gates": exit_gates,
                    "evidence_requirements": sorted(set(evidence)),
                    "failure_routes": failure_routes,
                }
            )
            previous_outputs = list(outputs)

        return ExecutionContract.from_mapping(
            {
                "contract_id": "FINAL_EXECUTION_CONTRACT",
                "contract_type": "universal_execution_contract",
                "version": "1.0.0",
                "source_activation_plan": ACTIVATION_PLAN_SOURCE,
                "terminal_doctrine": terminal_doctrine,
                "objective": intent.mission,
                "authority_order": authority_order,
                "kernel_activation": [binding.source_ref for binding in kernels],
                "execution_sequence": sequence,
                "validation_requirements": list(VALIDATION_REQUIREMENTS),
                "stop_conditions": list(STOP_CONDITIONS),
                "output_contract": list(OUTPUT_CONTRACT),
                "adapter_targets": list(ADAPTER_TARGETS),
                "metadata": {
                    "compiled_by": "l9_cognitive_runtime.compiler.execution",
                    "pipeline_id": pipeline_id,
                    "matched_route": plan.matched_route,
                    "confidence": plan.confidence,
                    "phase_kernels": phase_kernels,
                    # INV-014: active kernel semantic content is part of
                    # bundle provenance.
                    "kernel_digests": {
                        binding.source_ref: binding.source_digest for binding in kernels
                    },
                    "authority_order_source": (
                        task_context.authority.effective_order_source.value
                        if task_context is not None
                        else "compiler_default"
                    ),
                    "context_digest": context_digest or "",
                },
                "obligations": [
                    obligation.to_canonical_dict() for obligation in (obligations or [])
                ],
                "execution_steps": execution_steps,
            }
        )
