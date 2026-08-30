"""Explicit context requirement planning (INV-CTX-008).

Detailed context selection is never ad hoc: it is driven by a typed
``ContextRequirementPlan`` compiled *before* any item is looked at, from the
task scope, the bounded discovery projection, the matched route, and the
resolved kernel bindings.

Dependency direction matters as much as the output (A057): this module must
never import or consult ``ObligationDeriver`` or any downstream execution IR.
Requirements precede obligations; obligations may reference the closed context,
never the reverse. ``tests/test_architecture_invariants.py`` enforces that
mechanically.

Legacy compatibility rule (INV-CTX-040): a caller that supplies no governed
snapshot and no scope hints must keep compiling exactly as before. Requirements
are therefore optional by default and become *required* only when the task or
route explicitly needs external governed context — concretely, when the caller
named target references, or when discovery actually proved architecture
signals.
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.task_scope import scope_reference_set
from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.context import (
    AuthorityLevel,
    ContextBudget,
    ContextKind,
    ContextRequirement,
    ContextRequirementPlan,
    ContextScopeMode,
    CoverageMode,
    DiscoveryContext,
    FreshnessRequirement,
    MissingPolicy,
    TaskScope,
)

# Canonical global bounds for the union of unique selected snapshot items.
GLOBAL_MAX_ITEMS = 64
GLOBAL_MAX_BYTES = 262_144

# Deterministic priority ladder: governing context is planned before the
# material it governs, and enrichment is planned last.
PRIORITY = {
    ContextKind.ARCHITECTURE_CONSTRAINT: 10,
    ContextKind.APPLICABLE_LAW: 20,
    ContextKind.REPOSITORY_STATE: 30,
    ContextKind.RELEVANT_ENTITY: 40,
    ContextKind.DEPENDENCY_CONTEXT: 50,
    ContextKind.PRIOR_DECISION: 60,
    ContextKind.EVIDENCE_REF: 70,
    ContextKind.AUTHORITY_FACT: 80,
    ContextKind.CAPABILITY_FACT: 90,
    ContextKind.MEMORY_CONTEXT: 100,
}

PER_REQUIREMENT_MAX_ITEMS = 16

# Reduction happens through *matching* — kind, scope, and authority already
# exclude irrelevant material — so governed kinds admit everything eligible.
# Memory is the exception: it is non-authoritative and potentially unbounded,
# so it is the one kind capped by minimum coverage (INV-CTX-004).
MEMORY_MIN_ITEMS = 3
PER_REQUIREMENT_MAX_BYTES = 65_536


class ContextRequirementPlanner:
    """Compile the typed requirement plan that drives detailed selection."""

    def plan(
        self,
        intent: IntentContract,
        scope: TaskScope,
        discovery: DiscoveryContext,
        plan: ActivationPlan,
        kernels: list[KernelBinding],
    ) -> ContextRequirementPlan:
        scoped_refs = sorted(scope_reference_set(scope))
        has_targets = bool(scoped_refs)
        materiality_required = bool((plan.architecture_materiality or {}).get("required"))
        architecture_proven = bool(discovery.architecture_signal_refs)

        requirements: list[ContextRequirement] = []

        # Architecture constraints. Required only when materiality fired *and*
        # discovery proved governed architecture signals — mission tokens alone
        # never create a blocking external requirement (INV-CTX-014).
        architecture_required = materiality_required and architecture_proven
        requirements.append(
            self._requirement(
                kind=ContextKind.ARCHITECTURE_CONSTRAINT,
                reason=(
                    "architecture materiality proven by governed discovery signals"
                    if architecture_required
                    else "architecture constraints applicable to the task scope, if any"
                ),
                required=architecture_required,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=1 if architecture_required else 0,
                missing_policy=(
                    MissingPolicy.PRESERVE_UNKNOWN
                    if architecture_required
                    else MissingPolicy.OPTIONAL
                ),
            )
        )

        # Governing law applicable to this task scope. Selected, never dumped
        # (INV-CTX-015).
        requirements.append(
            self._requirement(
                kind=ContextKind.APPLICABLE_LAW,
                reason="law and governance rules applicable to the compiled task scope",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
            )
        )

        # Repository facts about the named subject. This is the one requirement
        # a caller can make blocking, by naming target references.
        requirements.append(
            self._requirement(
                kind=ContextKind.REPOSITORY_STATE,
                reason=(
                    "repository facts about the explicitly targeted references"
                    if has_targets
                    else "repository facts relevant to the task scope, if any"
                ),
                required=has_targets,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=1 if has_targets else 0,
                missing_policy=(
                    MissingPolicy.PRESERVE_UNKNOWN if has_targets else MissingPolicy.OPTIONAL
                ),
                scope_mode=ContextScopeMode.SCOPED if has_targets else ContextScopeMode.GLOBAL,
                scope_refs=scoped_refs if has_targets else [],
                minimum_authority=AuthorityLevel.GOVERNED_VERIFIED,
            )
        )

        requirements.append(
            self._requirement(
                kind=ContextKind.RELEVANT_ENTITY,
                reason="entities materially related to the task scope",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=ContextScopeMode.SCOPED if has_targets else ContextScopeMode.GLOBAL,
                scope_refs=scoped_refs if has_targets else [],
            )
        )

        requirements.append(
            self._requirement(
                kind=ContextKind.DEPENDENCY_CONTEXT,
                reason="dependency seams materially relevant to the task scope",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=ContextScopeMode.SCOPED if has_targets else ContextScopeMode.GLOBAL,
                scope_refs=scoped_refs if has_targets else [],
            )
        )

        requirements.append(
            self._requirement(
                kind=ContextKind.PRIOR_DECISION,
                reason="prior decisions governing the task scope, with supersession preserved",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
            )
        )

        requirements.append(
            self._requirement(
                kind=ContextKind.EVIDENCE_REF,
                reason="evidence supporting governed claims selected for this task",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                minimum_authority=AuthorityLevel.UNVERIFIED,
            )
        )

        requirements.append(
            self._requirement(
                kind=ContextKind.AUTHORITY_FACT,
                reason="proven authority grants and limits bearing on the compiled task",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
            )
        )

        requirements.append(
            self._requirement(
                kind=ContextKind.CAPABILITY_FACT,
                reason="proven capability availability bearing on the compiled task",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
            )
        )

        # Enrichment only, and ceilinged at informative authority by the model
        # itself (INV-CTX-019).
        requirements.append(
            self._requirement(
                kind=ContextKind.MEMORY_CONTEXT,
                reason="non-authoritative recall that may enrich, never resolve, the task",
                required=False,
                coverage_mode=CoverageMode.MINIMUM,
                min_items=MEMORY_MIN_ITEMS,
                missing_policy=MissingPolicy.OPTIONAL,
                minimum_authority=AuthorityLevel.INFORMATIVE,
                max_items=MEMORY_MIN_ITEMS,
            )
        )

        return ContextRequirementPlan(
            task_scope_digest=scope.sha256(),
            matched_route=plan.matched_route,
            global_budget=ContextBudget(
                max_total_items=GLOBAL_MAX_ITEMS,
                max_total_bytes=GLOBAL_MAX_BYTES,
            ),
            requirements=requirements,
        )

    @staticmethod
    def _requirement(
        *,
        kind: ContextKind,
        reason: str,
        required: bool,
        coverage_mode: CoverageMode,
        min_items: int,
        missing_policy: MissingPolicy,
        scope_mode: ContextScopeMode = ContextScopeMode.GLOBAL,
        scope_refs: list[str] | None = None,
        minimum_authority: AuthorityLevel = AuthorityLevel.INFORMATIVE,
        freshness_requirement: FreshnessRequirement = FreshnessRequirement.SNAPSHOT_BOUND,
        max_items: int = PER_REQUIREMENT_MAX_ITEMS,
    ) -> ContextRequirement:
        return ContextRequirement(
            context_kind=kind,
            reason=reason,
            required=required,
            scope_mode=scope_mode,
            scope_refs=scope_refs or [],
            freshness_requirement=freshness_requirement,
            coordinate_constraint=None,
            minimum_authority=minimum_authority,
            priority=PRIORITY[kind],
            coverage_mode=coverage_mode,
            min_items=min_items,
            required_semantic_keys=[],
            max_items=max_items,
            max_bytes=PER_REQUIREMENT_MAX_BYTES,
            missing_policy=missing_policy,
        )


__all__ = [
    "GLOBAL_MAX_BYTES",
    "GLOBAL_MAX_ITEMS",
    "PER_REQUIREMENT_MAX_BYTES",
    "PER_REQUIREMENT_MAX_ITEMS",
    "MEMORY_MIN_ITEMS",
    "PRIORITY",
    "ContextRequirementPlanner",
]
