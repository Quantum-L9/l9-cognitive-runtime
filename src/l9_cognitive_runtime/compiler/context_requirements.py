"""Explicit context requirement planning (INV-CTX-008).

Detailed context selection is never ad hoc: it is driven by a typed
``ContextRequirementPlan`` compiled *before* any item is looked at, from the
task scope, the bounded discovery projection, the matched route, and the
resolved kernel bindings.

Two properties are easy to lose here and are therefore explicit.

**Selected kernels really demand context.** Accepting ``kernels`` and then
never reading them would make kernel selection decorative: the bindings would
be copied into the compiled context while being unable to change what context
the compile requires. Each binding's declared ``context_needs`` is consumed
here and bound to the current task scope (INV-CTX-020).

**Scoped governing context survives detailed selection.** When the task names
scope references, governing requirements are planned as *task-scoped*, not
global. Planning them globally would exclude exactly the scoped constraint that
legally fired architecture materiality — proving materiality from an item and
then discarding it (INV-CTX-015). A globally applicable governed item still
satisfies a scoped governing requirement; an unrelated scope does not.

Dependency direction matters as much as the output: this module must never
import or consult ``ObligationDeriver`` or any downstream execution IR.
Requirements precede obligations; obligations may reference the closed context,
never the reverse. ``tests/test_architecture_invariants.py`` enforces that
mechanically.

Legacy compatibility rule (INV-CTX-040): a caller that supplies no governed
snapshot and no scope hints must keep compiling exactly as before. Requirements
are therefore optional by default and become *required* only when the task or
route explicitly needs external governed context — concretely, when the caller
named target references, when discovery actually proved architecture signals,
or when a selected kernel declared a required need.
"""

from __future__ import annotations

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding, KernelContextNeed
from l9_cognitive_runtime.compiler.task_scope import scope_reference_set
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
# material it governs, and enrichment is planned last. The ladder steps by 10
# so a kernel-demanded requirement can sit immediately after the baseline
# requirement for its kind without colliding with another kind.
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

KERNEL_NEED_PRIORITY_OFFSET = 1

# Governing kinds: their claims apply *to* a scope, so when the task names one
# they are planned scoped rather than global (INV-CTX-015).
GOVERNING_KINDS = (
    ContextKind.ARCHITECTURE_CONSTRAINT,
    ContextKind.APPLICABLE_LAW,
    ContextKind.PRIOR_DECISION,
    ContextKind.AUTHORITY_FACT,
)

PER_REQUIREMENT_MAX_ITEMS = 16

# Reduction happens through *matching* — kind, scope, and authority already
# exclude irrelevant material — so governed kinds admit everything eligible.
# Memory is the exception: it is non-authoritative and potentially unbounded,
# so it is the one kind capped by minimum coverage (INV-CTX-004).
MEMORY_MIN_ITEMS = 3
PER_REQUIREMENT_MAX_BYTES = 65_536


def _need_signature(need: KernelContextNeed) -> tuple[str, bool, str, str, str, tuple[str, ...]]:
    """Semantic identity of a need, so identical needs merge into one requirement."""
    return (
        need.context_kind.value,
        need.required,
        need.reason,
        need.coverage.value,
        need.minimum_authority.value,
        need.required_semantic_keys,
    )


class ContextRequirementPlanner:
    """Compile the typed requirement plan that drives detailed selection."""

    def plan(
        self,
        scope: TaskScope,
        discovery: DiscoveryContext,
        plan: ActivationPlan,
        kernels: list[KernelBinding],
    ) -> ContextRequirementPlan:
        scoped_refs = sorted(scope_reference_set(scope))
        has_targets = bool(scoped_refs)
        materiality_required = bool((plan.architecture_materiality or {}).get("required"))
        architecture_proven = bool(discovery.architecture_signal_refs)

        def governing_scope(kind: ContextKind) -> tuple[ContextScopeMode, list[str]]:
            """Scope binding for a requirement of this kind under this task."""
            if not has_targets:
                return ContextScopeMode.GLOBAL, []
            if kind in GOVERNING_KINDS or kind in {
                ContextKind.REPOSITORY_STATE,
                ContextKind.RELEVANT_ENTITY,
                ContextKind.DEPENDENCY_CONTEXT,
            }:
                return ContextScopeMode.SCOPED, scoped_refs
            return ContextScopeMode.GLOBAL, []

        requirements: list[ContextRequirement] = []

        # Architecture constraints. Required only when materiality fired *and*
        # discovery proved governed architecture signals — mission tokens alone
        # never create a blocking external requirement (INV-CTX-014).
        architecture_required = materiality_required and architecture_proven
        arch_mode, arch_refs = governing_scope(ContextKind.ARCHITECTURE_CONSTRAINT)
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
                scope_mode=arch_mode,
                scope_refs=arch_refs,
            )
        )

        # Governing law applicable to this task scope. Selected, never dumped
        # (INV-CTX-015).
        law_mode, law_refs = governing_scope(ContextKind.APPLICABLE_LAW)
        requirements.append(
            self._requirement(
                kind=ContextKind.APPLICABLE_LAW,
                reason="law and governance rules applicable to the compiled task scope",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=law_mode,
                scope_refs=law_refs,
            )
        )

        # Repository facts about the named subject. This is the one requirement
        # a caller can make blocking, by naming target references.
        state_mode, state_refs = governing_scope(ContextKind.REPOSITORY_STATE)
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
                scope_mode=state_mode,
                scope_refs=state_refs,
                minimum_authority=AuthorityLevel.GOVERNED_VERIFIED,
            )
        )

        entity_mode, entity_refs = governing_scope(ContextKind.RELEVANT_ENTITY)
        requirements.append(
            self._requirement(
                kind=ContextKind.RELEVANT_ENTITY,
                reason="entities materially related to the task scope",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=entity_mode,
                scope_refs=entity_refs,
            )
        )

        dep_mode, dep_refs = governing_scope(ContextKind.DEPENDENCY_CONTEXT)
        requirements.append(
            self._requirement(
                kind=ContextKind.DEPENDENCY_CONTEXT,
                reason="dependency seams materially relevant to the task scope",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=dep_mode,
                scope_refs=dep_refs,
            )
        )

        decision_mode, decision_refs = governing_scope(ContextKind.PRIOR_DECISION)
        requirements.append(
            self._requirement(
                kind=ContextKind.PRIOR_DECISION,
                reason="prior decisions governing the task scope, with supersession preserved",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=decision_mode,
                scope_refs=decision_refs,
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

        authority_mode, authority_refs = governing_scope(ContextKind.AUTHORITY_FACT)
        requirements.append(
            self._requirement(
                kind=ContextKind.AUTHORITY_FACT,
                reason="proven authority grants and limits bearing on the compiled task",
                required=False,
                coverage_mode=CoverageMode.ALL_ELIGIBLE,
                min_items=0,
                missing_policy=MissingPolicy.OPTIONAL,
                scope_mode=authority_mode,
                scope_refs=authority_refs,
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

        requirements.extend(self._kernel_requirements(kernels, has_targets, scoped_refs))

        return ContextRequirementPlan(
            task_scope_digest=scope.sha256(),
            matched_route=plan.matched_route,
            global_budget=ContextBudget(
                max_total_items=GLOBAL_MAX_ITEMS,
                max_total_bytes=GLOBAL_MAX_BYTES,
            ),
            requirements=requirements,
        )

    def _kernel_requirements(
        self,
        kernels: list[KernelBinding],
        has_targets: bool,
        scoped_refs: list[str],
    ) -> list[ContextRequirement]:
        """Turn every selected kernel's declared needs into real requirements.

        Identical needs from different kernels merge into one requirement that
        records every contributing kernel, so two kernels wanting the same thing
        do not produce two indistinguishable requirements.
        """
        merged: dict[tuple[str, bool, str, str, str, tuple[str, ...]], list[str]] = {}
        needs_by_signature: dict[
            tuple[str, bool, str, str, str, tuple[str, ...]], KernelContextNeed
        ] = {}
        for binding in kernels:
            for need in binding.context_needs:
                signature = _need_signature(need)
                needs_by_signature.setdefault(signature, need)
                merged.setdefault(signature, []).append(f"{binding.source_ref}#{need.need_id}")

        requirements: list[ContextRequirement] = []
        for signature in sorted(merged):
            need = needs_by_signature[signature]
            scope_mode = (
                ContextScopeMode.SCOPED
                if has_targets and need.context_kind is not ContextKind.MEMORY_CONTEXT
                else ContextScopeMode.GLOBAL
            )
            min_items = 0
            if need.coverage is CoverageMode.SEMANTIC_KEYS:
                min_items = len(need.required_semantic_keys)
            elif need.required:
                min_items = 1
            requirements.append(
                self._requirement(
                    kind=need.context_kind,
                    reason=need.reason,
                    required=need.required,
                    coverage_mode=need.coverage,
                    min_items=min_items,
                    missing_policy=(
                        MissingPolicy.PRESERVE_UNKNOWN if need.required else MissingPolicy.OPTIONAL
                    ),
                    scope_mode=scope_mode,
                    scope_refs=scoped_refs if scope_mode is ContextScopeMode.SCOPED else [],
                    minimum_authority=need.minimum_authority,
                    priority=PRIORITY[need.context_kind] + KERNEL_NEED_PRIORITY_OFFSET,
                    required_semantic_keys=list(need.required_semantic_keys),
                    max_items=max(PER_REQUIREMENT_MAX_ITEMS, min_items),
                    kernel_need_refs=sorted(merged[signature]),
                )
            )
        return requirements

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
        priority: int | None = None,
        required_semantic_keys: list[str] | None = None,
        kernel_need_refs: list[str] | None = None,
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
            priority=PRIORITY[kind] if priority is None else priority,
            coverage_mode=coverage_mode,
            min_items=min_items,
            required_semantic_keys=required_semantic_keys or [],
            max_items=max_items,
            max_bytes=PER_REQUIREMENT_MAX_BYTES,
            missing_policy=missing_policy,
            kernel_need_refs=kernel_need_refs or [],
        )


__all__ = [
    "GLOBAL_MAX_BYTES",
    "GLOBAL_MAX_ITEMS",
    "GOVERNING_KINDS",
    "KERNEL_NEED_PRIORITY_OFFSET",
    "MEMORY_MIN_ITEMS",
    "PER_REQUIREMENT_MAX_BYTES",
    "PER_REQUIREMENT_MAX_ITEMS",
    "PRIORITY",
    "ContextRequirementPlanner",
]
