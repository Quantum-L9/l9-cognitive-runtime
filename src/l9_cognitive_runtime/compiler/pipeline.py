"""The single live compilation spine (INV-001, INV-CTX-002).

Exactly one authoritative path composes fresh missions into a runtime bundle:

CompileRequest + ContextSnapshot -> ObjectiveDeriver -> TaskScopeCompiler ->
ContextDiscoveryCompiler -> ActivationPlanner -> KernelResolver ->
ContextRequirementPlanner -> ContextCompiler -> CompiledTaskContext ->
ContextClosureValidator -> ObligationDeriver -> ExecutionContractCompiler ->
ValidationContractCompiler -> HandoffContractCompiler ->
ExecutionGraphCompiler -> semantic digest -> ExecutionPacket ->
validate_packet -> BundleSemanticValidator -> RuntimeBundle.

All semantic inputs (routing rules, pipeline definition, kernels) are
resolved from the verified pack and fail closed when absent. Obligations are
derived once and conserved through every downstream IR (INV-003).

Two bounded context projections sit inside this spine (INV-CTX-005): discovery
before routing, and requirement-bound selection after kernel resolution.
Neither acquires anything — both project over the immutable ``ContextSnapshot``
the caller injected, whose finite input ceilings are enforced before any of it
is resolved. ``context_snapshot=None`` means an empty governed snapshot, which
is what every pre-context caller gets (INV-CTX-040).

This module is the **only** production composition owner (INV-CTX-002). The
legacy ``runtime/`` CLIs reach the same internal path through
:meth:`CompilePipeline.compile_from_root`; they do not sequence stages
themselves, and no compatibility entry can skip context closure, packet
validation, or runtime semantic liveness.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from l9_cognitive_runtime.compiler.activation import ActivationPlan, ActivationPlanner
from l9_cognitive_runtime.compiler.adapters import validate_packet
from l9_cognitive_runtime.compiler.context_closure import ContextClosureValidator
from l9_cognitive_runtime.compiler.context_requirements import ContextRequirementPlanner
from l9_cognitive_runtime.compiler.execution import AUTHORITY_ORDER, ExecutionContractCompiler
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
from l9_cognitive_runtime.compiler.packet import build_execution_packet
from l9_cognitive_runtime.compiler.task_context import (
    ContextCompiler,
    ContextDiscoveryCompiler,
    preflight_snapshot,
    resolve_snapshot,
)
from l9_cognitive_runtime.compiler.task_scope import TaskScopeCompiler
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
from l9_cognitive_runtime.models.context import ContextSnapshot
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackProvenance, RuntimePack
from l9_cognitive_runtime.parsing import load_yaml_file
from l9_cognitive_runtime.types import CompileRequest, RuntimeBundle

RULES_REL = "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml"
PIPELINE_REL = "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"

# Provenance label for a compatibility compile against a bare repository root.
# It is deliberately not an empty string: a blank digest reads as "verified with
# nothing", while this reads as what it is.
UNVERIFIED_ROOT_MANIFEST = "unverified:repository_root"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_version() -> str:
    """The canonical compiler package version (INV-CTX-032).

    Deferred to call time: ``l9_cognitive_runtime.__init__`` imports the service,
    which imports this module, so a top-level import would be circular. This is
    installed-artifact-safe and never touches ambient Git state.
    """
    from l9_cognitive_runtime import __version__

    return __version__


@dataclass(frozen=True)
class RootCompilation:
    """A compatibility compile against a bare repository root.

    Carries the plan and bindings alongside the bundle so the legacy ``runtime/``
    CLIs can project the slice they need without recomposing anything.
    """

    bundle: RuntimeBundle
    plan: ActivationPlan
    kernels: list[KernelBinding]


class CompilePipeline:
    """Compose the live compiler spine over a verified pack."""

    def compile(
        self,
        request: CompileRequest,
        pack: RuntimePack,
        *,
        context_snapshot: ContextSnapshot | None = None,
    ) -> RuntimeBundle:
        # pack.resolve fails closed when the routing sources are absent.
        return self._compile(
            request=request,
            rules_path=pack.resolve(RULES_REL),
            pipeline_path=pack.resolve(PIPELINE_REL),
            kernel_root=pack.provenance.root,
            provenance=pack.provenance,
            context_snapshot=context_snapshot,
        ).bundle

    def compile_from_root(
        self,
        root: Path,
        mission: str,
        *,
        task_type: str | None = None,
        include_terminal: bool = False,
        context_snapshot: ContextSnapshot | None = None,
        activation_plan: ActivationPlan | None = None,
    ) -> RootCompilation:
        """Compatibility entry for the legacy ``runtime/`` CLIs (INV-CTX-002).

        A bare repository root has no verified manifest, so this path exists
        only for those wrappers. It is not a second compiler: it joins the same
        internal path, so context closure, packet validation, and runtime
        semantic liveness all still run and cannot be bypassed.

        ``activation_plan`` supports the activation-plan-only CLI, which is
        handed a plan rather than routing one. The plan replaces routing; it
        replaces nothing else.
        """
        resolved = root.resolve()
        request = (
            CompileRequest(mission=mission, pack_root=resolved, task_type=task_type)
            if task_type is not None
            else CompileRequest(mission=mission, pack_root=resolved)
        )
        provenance = PackProvenance(
            pack_ref=str(resolved),
            root=resolved,
            manifest_digest=UNVERIFIED_ROOT_MANIFEST,
            file_digests={},
        )
        return self._compile(
            request=request,
            rules_path=resolved / RULES_REL,
            pipeline_path=resolved / PIPELINE_REL,
            kernel_root=resolved,
            provenance=provenance,
            context_snapshot=context_snapshot,
            include_terminal=include_terminal,
            activation_plan=activation_plan,
        )

    def _compile(
        self,
        *,
        request: CompileRequest,
        rules_path: Path,
        pipeline_path: Path,
        kernel_root: Path,
        provenance: PackProvenance,
        context_snapshot: ContextSnapshot | None,
        include_terminal: bool = False,
        activation_plan: ActivationPlan | None = None,
    ) -> RootCompilation:
        intent = ObjectiveDeriver().derive(request)
        snapshot = context_snapshot if context_snapshot is not None else ContextSnapshot.empty()
        # INV-CTX-007: bound the input before any of it is normalized, hashed,
        # grouped, or resolved.
        preflight_snapshot(snapshot)

        # Task scope from typed intent + normalized caller hints. Hints may
        # narrow scope; they never prove external facts (INV-CTX-006).
        scope = TaskScopeCompiler().compile(intent)
        # One resolution pass over the snapshot, shared by both projections, so
        # a contradiction resolves identically wherever it is consumed.
        resolution = resolve_snapshot(snapshot)
        discovery = ContextDiscoveryCompiler().compile(scope, resolution)

        plan = activation_plan or ActivationPlanner().plan(
            intent,
            rules_path=rules_path,
            pipeline_path=pipeline_path,
            discovery=discovery,
            include_terminal=include_terminal,
        )
        kernels = KernelResolver().resolve(plan.active_kernels, kernel_root)
        pipeline = load_yaml_file(pipeline_path)

        # Requirements are planned from scope/route/kernels only — never from
        # obligations, which are derived below.
        requirement_plan = ContextRequirementPlanner().plan(scope, discovery, plan, kernels)
        task_context = ContextCompiler().compile(
            intent=intent,
            scope=scope,
            resolution=resolution,
            discovery=discovery,
            requirement_plan=requirement_plan,
            activation=plan,
            kernels=kernels,
            package_version=_package_version(),
            default_authority_order=AUTHORITY_ORDER,
        )
        # INV-CTX-025: context closure precedes every execution semantic.
        closure_report = ContextClosureValidator().validate(
            context=task_context,
            requirement_plan=requirement_plan,
            resolution=resolution,
            kernels=kernels,
        )
        context_digest = task_context.sha256()

        # INV-003: derive obligations once, then conserve them through every IR.
        obligations = ObligationDeriver().derive(intent, plan, kernels, task_context)
        validate_obligations(obligations, owner_registry(plan, kernels), stage="intent")
        intent.obligations = obligations

        execution = ExecutionContractCompiler().compile(
            intent,
            plan,
            kernels,
            pipeline,
            obligations,
            task_context=task_context,
            context_digest=context_digest,
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
        semantic_payload = self._semantic_payload(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            kernels=kernels,
            rules_path=rules_path,
            pipeline_path=pipeline_path,
            context_digest=context_digest,
        )
        semantic_digest = sha256_digest(canonical_json(semantic_payload))
        packet = build_execution_packet(
            intent=intent,
            kernels=kernels,
            plan=plan,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            routing_rules_digest=_file_sha256(rules_path),
            pipeline_digest=_file_sha256(pipeline_path),
            semantic_digest=semantic_digest,
            task_context=task_context,
            context_digest=context_digest,
        )
        # INV-013: the packet is the hand-off surface, so it is validated on
        # every fresh compile — not only when an adapter is rendered.
        validate_packet(packet)
        # BundleSemanticValidator: compile-time semantic liveness, fail closed.
        # Runs last so it can judge the packet alongside the compiled IRs.
        validate_runtime_semantic_liveness(
            intent=intent,
            plan=plan,
            kernels=kernels,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            task_context=task_context,
            context_digest=context_digest,
            closure_report=closure_report,
            packet=packet,
            semantic_payload=semantic_payload,
        )
        bundle = RuntimeBundle(
            intent=intent,
            execution=execution,
            validation=validation,
            handoff=handoff,
            graph=graph,
            provenance=provenance,
            semantic_digest=semantic_digest,
            packet=packet,
            task_context=task_context,
        )
        return RootCompilation(bundle=bundle, plan=plan, kernels=kernels)

    @staticmethod
    def _semantic_payload(
        *,
        intent: IntentContract,
        execution: ExecutionContract,
        validation: ValidationContract,
        handoff: HandoffContract,
        graph: ExecutionGraph,
        kernels: list[KernelBinding],
        rules_path: Path,
        pipeline_path: Path,
        context_digest: str,
    ) -> dict[str, object]:
        """Bundle semantic digest payload over every provenance-contract input.

        Active kernel digests participate (canonical order); inactive kernel
        content does not. Compiler IR digests stand in for compiler semantics.
        The compiled-context digest is an added input, never a replacement:
        material context change moves runtime semantic identity even when the
        task text is unchanged (INV-CTX-029).
        """
        return {
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
            "context_digest": context_digest,
        }
