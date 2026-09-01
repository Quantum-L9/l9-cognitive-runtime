"""Bounded context discovery and requirement-driven context compilation.

Two bounded projections over one immutable injected snapshot (INV-CTX-005) —
never a search loop, never an acquisition loop, never reasoning:

1. :class:`ContextDiscoveryCompiler` — just enough governed fact to route the
   task and decide architecture materiality.
2. :class:`ContextCompiler` — the requirement-bound projection that produces
   the canonical :class:`CompiledTaskContext`.

Everything here is deterministic. The properties that are easy to lose and are
therefore stated explicitly:

- **Input is bounded before it is resolved.** ``preflight_snapshot`` rejects an
  oversized snapshot on item count before anything is hashed, and on canonical
  byte size before resolution (INV-CTX-007). Nothing is silently truncated.
- **Explicit supersession is resolved kind-wide, first.** Grouping by semantic
  key before supersession would mean a law can only ever supersede a law with
  its own id — which is not what supersession means (INV-CTX-013).
- **Input order is never precedence.** Surviving candidates are grouped by
  ``(kind, semantic_key)``, deduplicated by canonical claim, and resolved by
  the kind's own domain rule. An equal-authority contradiction becomes a
  ``ContextUnknown`` — never an arbitrary pick.
- **Nothing is selected for padding.** An item enters only by satisfying a
  requirement, and carries the requirement in ``selected_because``.
- **Absence is never a grant.** A required capability or authority with no
  proving fact stays an explicit unknown (INV-CTX-021/022).
- **Budgets never silently truncate.** Overflow routes through the affected
  requirement's declared missing policy (INV-CTX-026).

This module performs no I/O of any kind (INV-CTX-033).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from l9_cognitive_runtime.compiler.activation import ActivationPlan
from l9_cognitive_runtime.compiler.kernels import KernelBinding
from l9_cognitive_runtime.compiler.task_scope import scope_reference_set
from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.canonical import sha256_digest
from l9_cognitive_runtime.models.context import (
    AUTHORITY_RANK,
    CONTEXT_COMPILER_SEMANTICS_VERSION,
    SNAPSHOT_MAX_BYTES,
    SNAPSHOT_MAX_ITEMS,
    ApplicableLaw,
    AuthorityContext,
    AuthorityFact,
    AuthorityLevel,
    AuthorityRequirement,
    CapabilityContext,
    CapabilityFact,
    CapabilityRequirement,
    CompiledTaskContext,
    CompilerIdentity,
    ContextItemIdentity,
    ContextKind,
    ContextProvenance,
    ContextRequirement,
    ContextRequirementPlan,
    ContextScopeMode,
    ContextSnapshot,
    ContextUnknown,
    CoverageMode,
    DecisionStatus,
    DependencyContext,
    DiscoveryContext,
    EffectiveAuthorityOrderSource,
    EntityContext,
    EvidenceRef,
    FreshnessRequirement,
    GovernedConstraint,
    MemoryContext,
    MissingPolicy,
    PriorDecision,
    RepositoryState,
    TaskScope,
    UnknownMateriality,
    UnknownReasonCode,
    canonical_cost,
)
from l9_cognitive_runtime.models.errors import InvalidValueError

# Kinds the bounded discovery projection may consider. Memory is absent by
# construction: it can never be an authoritative routing input (INV-CTX-019).
DISCOVERY_KINDS = (
    ContextKind.RELEVANT_ENTITY,
    ContextKind.REPOSITORY_STATE,
    ContextKind.ARCHITECTURE_CONSTRAINT,
    ContextKind.APPLICABLE_LAW,
    ContextKind.DEPENDENCY_CONTEXT,
)

# Kinds whose claims legitimately apply beyond a single reference, so a global
# candidate may satisfy a scoped requirement. Repository facts, entities,
# dependencies, evidence, and memory are about *something* and must be scoped.
GLOBALLY_APPLICABLE_KINDS = frozenset(
    {
        ContextKind.ARCHITECTURE_CONSTRAINT,
        ContextKind.APPLICABLE_LAW,
        ContextKind.PRIOR_DECISION,
        ContextKind.AUTHORITY_FACT,
        ContextKind.CAPABILITY_FACT,
    }
)

# Kinds that carry explicit supersession, and the domain identifier that
# supersession references name. These are resolved kind-wide before any
# same-semantic-key resolution runs (INV-CTX-013).
SUPERSESSION_KINDS: dict[ContextKind, str] = {
    ContextKind.APPLICABLE_LAW: "law_id",
    ContextKind.PRIOR_DECISION: "decision_id",
}


def preflight_snapshot(snapshot: ContextSnapshot) -> None:
    """Enforce the finite input ceilings before anything is resolved.

    Item count is checked first and costs nothing per item, so an oversized
    snapshot is rejected before any candidate is canonicalized, hashed, grouped,
    or resolved. Byte size is measured canonically and deterministically. Both
    breaches fail closed: input is never silently truncated (INV-CTX-007).
    """
    count = snapshot.item_count()
    if count > SNAPSHOT_MAX_ITEMS:
        raise InvalidValueError(
            "context snapshot exceeds the maximum item count",
            path="context_snapshot",
            details={"items": count, "max_items": SNAPSHOT_MAX_ITEMS},
        )
    size = snapshot.canonical_byte_size()
    if size > SNAPSHOT_MAX_BYTES:
        raise InvalidValueError(
            "context snapshot exceeds the maximum canonical byte size",
            path="context_snapshot",
            details={"bytes": size, "max_bytes": SNAPSHOT_MAX_BYTES},
        )


def _claim_digest_payload(item: ContextItemIdentity) -> dict[str, Any]:
    return item.claim_payload()


def _representative(items: Sequence[ContextItemIdentity]) -> ContextItemIdentity:
    """Pick the canonical carrier of a byte-identical claim.

    Never by list position: strongest authority, then a present immutable
    coordinate, then coordinate, then content digest, then item id.
    """
    return min(
        items,
        key=lambda item: (
            item.authority_rank,
            0 if item.source_ref.immutable_coordinate else 1,
            item.source_ref.immutable_coordinate or "",
            item.source_ref.content_digest or "",
            item.item_id,
        ),
    )


def _strongest(items: Sequence[ContextItemIdentity]) -> list[ContextItemIdentity]:
    best = min(item.authority_rank for item in items)
    return [item for item in items if item.authority_rank == best]


class GroupResolution:
    """The outcome of resolving one ``(kind, semantic_key)`` group."""

    __slots__ = ("items", "conflict", "details", "sources")

    def __init__(
        self,
        items: list[ContextItemIdentity],
        conflict: bool,
        details: dict[str, Any] | None = None,
        sources: list[ContextItemIdentity] | None = None,
    ) -> None:
        self.items = items
        self.conflict = conflict
        self.details = details or {}
        self.sources = sources or []


@dataclass(frozen=True)
class SnapshotResolution:
    """One resolution pass over a snapshot, shared by both projections."""

    groups: dict[tuple[str, str], GroupResolution]
    supersession_unknowns: tuple[ContextUnknown, ...] = field(default=())


# --------------------------------------------------------------------------
# Kind-wide explicit supersession (INV-CTX-013).
# --------------------------------------------------------------------------


def _domain_id(item: ContextItemIdentity, attribute: str) -> str:
    return str(getattr(item, attribute))


def _supersession_targets(
    members: Sequence[ContextItemIdentity], attribute: str
) -> dict[str, set[str]]:
    """Map every name a claim can be referenced by to its domain identifiers."""
    targets: dict[str, set[str]] = {}
    for item in members:
        domain = _domain_id(item, attribute)
        for name in (domain, item.item_id):
            targets.setdefault(name, set()).add(domain)
    return targets


def _reaches_itself(node: str, adjacency: dict[str, set[str]]) -> bool:
    """True when ``node`` is reachable from itself along supersession edges."""
    seen: set[str] = set()
    stack = list(adjacency.get(node, ()))
    while stack:
        current = stack.pop()
        if current == node:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, ()))
    return False


def _resolve_supersession(
    members: Sequence[ContextItemIdentity], attribute: str, kind: ContextKind
) -> tuple[list[ContextItemIdentity], list[ContextUnknown]]:
    """Apply explicit supersession across the whole kind, order-independently."""
    targets = _supersession_targets(members, attribute)
    edges: set[tuple[str, str]] = set()
    dangling: set[tuple[str, str]] = set()

    for item in members:
        domain = _domain_id(item, attribute)
        for ref in getattr(item, "supersedes_refs", []):
            named = targets.get(str(ref))
            if not named:
                dangling.add((domain, str(ref)))
                continue
            # A claim may not supersede itself; only a sibling identity can.
            edges.update((domain, other) for other in named if other != domain)
        for ref in getattr(item, "superseded_by_refs", []):
            named = targets.get(str(ref))
            if not named:
                dangling.add((domain, str(ref)))
                continue
            edges.update((other, domain) for other in named if other != domain)

    adjacency: dict[str, set[str]] = {}
    for superseder, superseded in edges:
        adjacency.setdefault(superseder, set()).add(superseded)

    on_cycle = {node for node in adjacency if _reaches_itself(node, adjacency)}
    # A claim whose own standing is unresolvable must not silently kill a claim
    # whose standing is resolvable, so cycle members supersede nothing.
    superseded_domains = {
        superseded for superseder, superseded in edges if superseder not in on_cycle
    }

    unknowns: list[ContextUnknown] = [
        ContextUnknown(
            semantic_key=domain,
            reason_code=UnknownReasonCode.UNKNOWN_SUPERSESSION,
            materiality=UnknownMateriality.BLOCKING,
            details={
                "context_kind": kind.value,
                "reason": "supersession cycle",
                "cycle_members": sorted(on_cycle),
            },
        )
        for domain in sorted(on_cycle)
    ]
    unknowns.extend(
        ContextUnknown(
            semantic_key=domain,
            reason_code=UnknownReasonCode.DANGLING_SUPERSESSION,
            materiality=UnknownMateriality.NON_BLOCKING,
            details={"context_kind": kind.value, "unresolved_ref": ref},
        )
        for domain, ref in sorted(dangling)
    )

    survivors: list[ContextItemIdentity] = []
    for item in members:
        domain = _domain_id(item, attribute)
        if domain in on_cycle:
            continue
        if isinstance(item, PriorDecision) and item.status is DecisionStatus.SUPERSEDED:
            # An explicit superseded status never remains active (INV-CTX-016).
            continue
        if domain in superseded_domains:
            continue
        survivors.append(item)
    return survivors, unknowns


def apply_supersession(
    items: Sequence[ContextItemIdentity],
) -> tuple[list[ContextItemIdentity], list[ContextUnknown]]:
    """Resolve explicit supersession for every kind that declares it."""
    by_kind: dict[ContextKind, list[ContextItemIdentity]] = {}
    for item in items:
        by_kind.setdefault(item.context_kind, []).append(item)

    survivors: list[ContextItemIdentity] = []
    unknowns: list[ContextUnknown] = []
    for kind, members in by_kind.items():
        attribute = SUPERSESSION_KINDS.get(kind)
        if attribute is None:
            survivors.extend(members)
            continue
        kept, kind_unknowns = _resolve_supersession(members, attribute, kind)
        survivors.extend(kept)
        unknowns.extend(kind_unknowns)
    return survivors, unknowns


# --------------------------------------------------------------------------
# Same-semantic-key resolution over the surviving claims.
# --------------------------------------------------------------------------


def _resolve_group(kind: ContextKind, reps: list[ContextItemIdentity]) -> GroupResolution:
    """Apply the kind's domain precedence rule to competing same-key claims."""
    if len(reps) == 1:
        return GroupResolution(list(reps), conflict=False)

    if kind in {ContextKind.EVIDENCE_REF, ContextKind.MEMORY_CONTEXT}:
        # Evidence supports claims and memory enriches them; neither resolves
        # domain truth, so distinct same-key items simply coexist.
        return GroupResolution(sorted(reps, key=lambda item: item.sort_key), conflict=False)

    if kind is ContextKind.APPLICABLE_LAW:
        return _resolve_law([item for item in reps if isinstance(item, ApplicableLaw)])

    if kind is ContextKind.REPOSITORY_STATE:
        revisions = {item.revision for item in reps if isinstance(item, RepositoryState)}
        if len(revisions) > 1:
            # Differing revision coordinates do not imply recency.
            return GroupResolution(
                [], conflict=True, details={"revisions": sorted(revisions)}, sources=list(reps)
            )
        return _resolve_by_authority(reps)

    if kind is ContextKind.DEPENDENCY_CONTEXT:
        versions = {
            item.version_or_revision for item in reps if isinstance(item, DependencyContext)
        }
        if len(versions) > 1:
            # A higher version string does not imply governed precedence.
            return GroupResolution(
                [],
                conflict=True,
                details={"versions": sorted(str(v) for v in versions)},
                sources=list(reps),
            )
        return _resolve_by_authority(reps)

    return _resolve_by_authority(reps)


def _resolve_by_authority(reps: Sequence[ContextItemIdentity]) -> GroupResolution:
    top = _strongest(reps)
    if len(top) == 1:
        return GroupResolution(list(top), conflict=False)
    return GroupResolution(
        [],
        conflict=True,
        details={"authority_level": top[0].authority_level.value, "claims": len(top)},
        sources=list(reps),
    )


def _resolve_law(reps: list[ApplicableLaw]) -> GroupResolution:
    """Same-key law resolution. Supersession already ran kind-wide."""
    if len(reps) == 1:
        return GroupResolution(list(reps), conflict=False)
    candidates: list[ApplicableLaw] = list(reps)
    # Declared numeric precedence outranks generic authority rank.
    if candidates and all(item.precedence is not None for item in candidates):
        best = min(item.precedence or 0 for item in candidates)
        top = [item for item in candidates if item.precedence == best]
        if len(top) == 1:
            return GroupResolution(list(top), conflict=False)
        candidates = top
    return _resolve_by_authority(candidates)


def resolve_snapshot(snapshot: ContextSnapshot) -> SnapshotResolution:
    """Resolve supersession, then normalize, deduplicate, and resolve groups.

    Runs once per compile and is independent of the requirement plan, so the
    same contradiction resolves identically no matter which requirement
    consumes it.
    """
    survivors, supersession_unknowns = apply_supersession(snapshot.all_items())

    grouped: dict[tuple[str, str], list[ContextItemIdentity]] = {}
    for item in survivors:
        grouped.setdefault((item.context_kind.value, item.semantic_key), []).append(item)

    resolutions: dict[tuple[str, str], GroupResolution] = {}
    for key, items in grouped.items():
        by_claim: dict[str, list[ContextItemIdentity]] = {}
        for item in items:
            by_claim.setdefault(sha256_digest(_claim_digest_payload(item)), []).append(item)
        reps = [_representative(bucket) for bucket in by_claim.values()]
        reps.sort(key=lambda item: item.sort_key)
        resolutions[key] = _resolve_group(ContextKind(key[0]), reps)
    return SnapshotResolution(
        groups=resolutions,
        supersession_unknowns=tuple(supersession_unknowns),
    )


class ContextDiscoveryCompiler:
    """Bounded projection #1: governed fact sufficient to route (INV-CTX-014).

    The output is the *only* legal external proof of architecture materiality.
    Raw ``source_context.context_signals`` never reaches this far.

    It consumes the *resolved* snapshot, never the raw one: taking the raw
    snapshot as well would let a later edit route from candidates that
    supersession and deduplication had already removed.
    """

    def compile(
        self,
        scope: TaskScope,
        resolution: SnapshotResolution,
    ) -> DiscoveryContext:
        scoped_refs = scope_reference_set(scope)
        routing_refs: list[str] = []
        signal_refs: list[str] = []
        digests: dict[str, str] = {}
        unknowns: list[ContextUnknown] = list(resolution.supersession_unknowns)

        for kind in DISCOVERY_KINDS:
            for (kind_value, semantic_key), group in sorted(resolution.groups.items()):
                if kind_value != kind.value:
                    continue
                if group.conflict:
                    unknowns.append(
                        ContextUnknown(
                            semantic_key=semantic_key,
                            reason_code=UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS,
                            materiality=UnknownMateriality.NON_BLOCKING,
                            details={"context_kind": kind_value, **group.details},
                            source_refs=[item.source_ref for item in group.sources],
                        )
                    )
                    continue
                for item in group.items:
                    # Only governed facts route. Informative or unverified
                    # material may enrich later, never decide routing.
                    if item.authority_level not in {
                        AuthorityLevel.GOVERNED_AUTHORITATIVE,
                        AuthorityLevel.GOVERNED_VERIFIED,
                    }:
                        continue
                    if not _discovery_scope_match(item, scoped_refs):
                        continue
                    routing_refs.append(item.item_id)
                    digests[item.item_id] = item.candidate_digest()
                    if isinstance(item, GovernedConstraint):
                        # The proven signal name, provenance-bound through
                        # selected_item_digests[item_id].
                        signal_refs.append(item.constraint_id)

        return DiscoveryContext(
            task_scope_digest=scope.sha256(),
            routing_fact_refs=routing_refs,
            architecture_signal_refs=signal_refs,
            unresolved_unknowns=_dedupe_unknowns(unknowns),
            selected_item_digests=dict(sorted(digests.items())),
        )


def _discovery_scope_match(item: ContextItemIdentity, scoped_refs: frozenset[str]) -> bool:
    if item.scope_mode is ContextScopeMode.GLOBAL:
        return True
    return bool(set(item.scope_refs) & scoped_refs)


def matches_requirement(requirement: ContextRequirement, item: ContextItemIdentity) -> bool:
    """Explicit candidate matching. No implicit empty-list semantics.

    Public because context closure must judge *eligibility* with exactly the
    same rule the compiler selected with — a conflict that a requirement would
    have matched must be disposed even when nothing was selected for that key.
    """
    if item.context_kind is not requirement.context_kind:
        return False
    if item.authority_rank > AUTHORITY_RANK[requirement.minimum_authority]:
        return False
    if requirement.scope_mode is ContextScopeMode.GLOBAL:
        if item.scope_mode is not ContextScopeMode.GLOBAL:
            return False
    else:
        if item.scope_mode is ContextScopeMode.SCOPED:
            if not (set(item.scope_refs) & set(requirement.scope_refs)):
                return False
        elif requirement.context_kind not in GLOBALLY_APPLICABLE_KINDS:
            return False
    if requirement.freshness_requirement is FreshnessRequirement.EXACT_REVISION:
        constraint = requirement.coordinate_constraint
        coordinate = item.source_ref.immutable_coordinate
        revision = getattr(item, "revision", None)
        if constraint not in {coordinate, revision}:
            return False
    return True


def _candidate_sort_key(item: ContextItemIdentity) -> tuple[int, int, str, str]:
    return (
        0 if item.scope_mode is ContextScopeMode.SCOPED else 1,
        item.authority_rank,
        item.semantic_key,
        item.item_id,
    )


class _Selection:
    """Mutable selection state shared across requirements in one compile."""

    def __init__(self, plan: ContextRequirementPlan) -> None:
        self.plan = plan
        self.by_item: dict[str, ContextItemIdentity] = {}
        self.reasons: dict[str, set[str]] = {}
        self.total_bytes = 0

    def would_exceed_global(self, item: ContextItemIdentity, cost: int) -> bool:
        if item.item_id in self.by_item:
            return False  # already paid for; a reused item costs once
        budget = self.plan.global_budget
        if len(self.by_item) + 1 > budget.max_total_items:
            return True
        return self.total_bytes + cost > budget.max_total_bytes

    def admit(self, item: ContextItemIdentity, cost: int, requirement_id: str) -> None:
        if item.item_id not in self.by_item:
            self.by_item[item.item_id] = item
            self.total_bytes += cost
        self.reasons.setdefault(item.item_id, set()).add(requirement_id)


class ContextCompiler:
    """Bounded projection #2: the requirement-bound canonical context IR.

    Like discovery, it selects from the *resolved* snapshot only. The raw
    snapshot is deliberately out of reach so nothing here can select a
    candidate that supersession or deduplication already removed.
    """

    def compile(
        self,
        *,
        intent: IntentContract,
        scope: TaskScope,
        resolution: SnapshotResolution,
        discovery: DiscoveryContext,
        requirement_plan: ContextRequirementPlan,
        activation: ActivationPlan,
        kernels: list[KernelBinding],
        package_version: str,
        default_authority_order: Sequence[str],
    ) -> CompiledTaskContext:
        selection = _Selection(requirement_plan)
        unknowns: list[ContextUnknown] = list(scope.unresolved_unknowns)
        unknowns.extend(discovery.unresolved_unknowns)

        for requirement in requirement_plan.requirements:
            unknowns.extend(self._select_for(requirement, resolution, selection))

        selected = [
            item.model_copy(update={"selected_because": sorted(selection.reasons[item_id])})
            for item_id, item in sorted(selection.by_item.items())
        ]
        selected.sort(key=lambda item: item.sort_key)

        unknowns.extend(_unknown_status_decisions(selected))

        capabilities, capability_unknowns = _compile_capabilities(
            intent, activation, kernels, selected
        )
        authority, authority_unknowns = _compile_authority(
            intent, scope, activation, kernels, selected, default_authority_order
        )
        unknowns.extend(capability_unknowns)
        unknowns.extend(authority_unknowns)

        provenance = ContextProvenance(
            task_scope_digest=scope.sha256(),
            discovery_digest=discovery.sha256(),
            context_requirements_digest=requirement_plan.sha256(),
            discovery_item_digests=dict(discovery.selected_item_digests),
            selected_item_digests={item.item_id: item.candidate_digest() for item in selected},
            kernel_digests={binding.source_ref: binding.source_digest for binding in kernels},
            compiler_identity=CompilerIdentity(
                package_version=package_version,
                semantics_version=CONTEXT_COMPILER_SEMANTICS_VERSION,
            ),
        )

        return CompiledTaskContext(
            task_scope=scope,
            relevant_entities=_of_type(selected, EntityContext),
            repository_state=_of_type(selected, RepositoryState),
            architecture_constraints=_of_type(selected, GovernedConstraint),
            applicable_law=_of_type(selected, ApplicableLaw),
            prior_decisions=_of_type(selected, PriorDecision),
            dependency_context=_of_type(selected, DependencyContext),
            evidence_refs=_of_type(selected, EvidenceRef),
            memory_context=_of_type(selected, MemoryContext),
            # INV-CTX-020: byte-for-byte the bindings used downstream.
            selected_kernels=[binding.to_dict() for binding in kernels],
            capabilities=capabilities,
            authority=authority,
            unresolved_unknowns=_dedupe_unknowns(unknowns),
            provenance=provenance,
        )

    def _select_for(
        self,
        requirement: ContextRequirement,
        resolution: SnapshotResolution,
        selection: _Selection,
    ) -> list[ContextUnknown]:
        unknowns: list[ContextUnknown] = []
        eligible: list[ContextItemIdentity] = []
        conflicted_keys: list[tuple[str, GroupResolution]] = []

        for (kind_value, semantic_key), group in sorted(resolution.groups.items()):
            if kind_value != requirement.context_kind.value:
                continue
            if group.conflict:
                # Eligibility is judged from the competing sources: a conflict
                # this requirement would never have matched is not its problem,
                # and one it would have matched must be disposed explicitly.
                if any(matches_requirement(requirement, item) for item in group.sources):
                    conflicted_keys.append((semantic_key, group))
                continue
            eligible.extend(item for item in group.items if matches_requirement(requirement, item))

        eligible.sort(key=_candidate_sort_key)

        # An unresolved same-key contradiction is a disposition, not a silent
        # drop: it becomes an Unknown bound to the requirement that wanted it.
        disposed_keys: set[str] = set()
        for semantic_key, group in conflicted_keys:
            disposed_keys.add(semantic_key)
            unknowns.append(
                ContextUnknown(
                    requirement_ref=requirement.requirement_id,
                    semantic_key=semantic_key,
                    reason_code=UnknownReasonCode.CONFLICTING_GOVERNED_CLAIMS,
                    materiality=_materiality_for(requirement),
                    details={
                        "context_kind": requirement.context_kind.value,
                        **group.details,
                    },
                    source_refs=[item.source_ref for item in group.sources],
                )
            )

        selected_keys: set[str] = set()
        selected_count = 0
        requirement_bytes = 0
        budget_blocked = False

        for item in eligible:
            if (
                requirement.coverage_mode is CoverageMode.MINIMUM
                and selected_count >= requirement.min_items
            ):
                break
            if (
                requirement.coverage_mode is CoverageMode.SEMANTIC_KEYS
                and item.semantic_key not in requirement.required_semantic_keys
            ):
                continue
            cost = canonical_cost(item)
            if requirement.max_items is not None and selected_count + 1 > requirement.max_items:
                budget_blocked = True
                break
            if (
                requirement.max_bytes is not None
                and requirement_bytes + cost > requirement.max_bytes
            ):
                budget_blocked = True
                break
            if selection.would_exceed_global(item, cost):
                budget_blocked = True
                break
            selection.admit(item, cost, requirement.requirement_id)
            selected_keys.add(item.semantic_key)
            selected_count += 1
            requirement_bytes += cost

        satisfied = self._satisfied(
            requirement, selected_count, selected_keys, disposed_keys, budget_blocked
        )
        if not satisfied:
            unknowns.extend(
                self._dispose_unsatisfied(
                    requirement,
                    budget_blocked=budget_blocked,
                    selected_keys=selected_keys,
                    disposed_keys=disposed_keys,
                )
            )
        return unknowns

    @staticmethod
    def _satisfied(
        requirement: ContextRequirement,
        selected_count: int,
        selected_keys: set[str],
        disposed_keys: set[str],
        budget_blocked: bool,
    ) -> bool:
        if selected_count < requirement.min_items:
            return False
        if requirement.coverage_mode is CoverageMode.SEMANTIC_KEYS:
            missing = set(requirement.required_semantic_keys) - selected_keys - disposed_keys
            return not missing
        if requirement.coverage_mode is CoverageMode.ALL_ELIGIBLE:
            # `all_eligible` only breaks early on budget exhaustion, so a
            # budget stop is exactly the case where coverage is incomplete.
            return not budget_blocked
        return True

    @staticmethod
    def _dispose_unsatisfied(
        requirement: ContextRequirement,
        *,
        budget_blocked: bool,
        selected_keys: set[str],
        disposed_keys: set[str],
    ) -> list[ContextUnknown]:
        reason = (
            UnknownReasonCode.BUDGET_INSUFFICIENT
            if budget_blocked
            else UnknownReasonCode.MISSING_REQUIRED_CONTEXT
        )
        details: dict[str, Any] = {
            "context_kind": requirement.context_kind.value,
            "coverage_mode": requirement.coverage_mode.value,
            "min_items": requirement.min_items,
            "selected": len(selected_keys),
        }
        if requirement.coverage_mode is CoverageMode.SEMANTIC_KEYS:
            details["missing_semantic_keys"] = sorted(
                set(requirement.required_semantic_keys) - selected_keys - disposed_keys
            )
        if requirement.missing_policy is MissingPolicy.BLOCK:
            raise InvalidValueError(
                "required context could not be satisfied under a BLOCK missing policy",
                path=requirement.requirement_id,
                details={"reason_code": reason.value, **details},
            )
        if requirement.missing_policy is MissingPolicy.OPTIONAL:
            return []
        return [
            ContextUnknown(
                requirement_ref=requirement.requirement_id,
                reason_code=reason,
                materiality=_materiality_for(requirement),
                details=details,
            )
        ]


def _materiality_for(requirement: ContextRequirement) -> UnknownMateriality:
    return UnknownMateriality.BLOCKING if requirement.required else UnknownMateriality.NON_BLOCKING


def _unknown_status_decisions(selected: Sequence[ContextItemIdentity]) -> list[ContextUnknown]:
    """A decision whose status is itself unknown stays visible (INV-CTX-016)."""
    return [
        ContextUnknown(
            semantic_key=item.semantic_key,
            reason_code=UnknownReasonCode.UNKNOWN_SUPERSESSION,
            materiality=UnknownMateriality.BLOCKING,
            details={"decision_id": item.decision_id, "reason": "decision status unknown"},
            source_refs=[item.source_ref],
        )
        for item in selected
        if isinstance(item, PriorDecision) and item.status is DecisionStatus.UNKNOWN
    ]


def _of_type(items: Iterable[ContextItemIdentity], model: type) -> list[Any]:
    return [item for item in items if isinstance(item, model)]


def _dedupe_unknowns(unknowns: Iterable[ContextUnknown]) -> list[ContextUnknown]:
    indexed = {unknown.unknown_id: unknown for unknown in unknowns}
    return [indexed[key] for key in sorted(indexed)]


# --------------------------------------------------------------------------
# Capability and authority compilation.
#
# Requirements are compiler-derived from intent, scope, route, and kernels
# (INV-CTX-021/022). A snapshot proves *state*; it can never declare what the
# task requires — the models make that structurally impossible, since
# CapabilityFact.state and AuthorityFact.state have no ``required`` member.
#
# The disposition ladder is exhaustive on purpose: proven-negative blocks,
# proven-positive satisfies, and *absence* is its own explicit non-blocking
# state. Reasoning about gaps only when some fact happens to exist would make
# the empty snapshot silently permissive, which is precisely the shape that
# lets a successful compile imply a permission nobody proved.
# --------------------------------------------------------------------------

# Capability dispositions that count as explicitly recorded. Mirrored by the
# context closure validator, which proves each requirement reached exactly one.
CAPABILITY_STATES = ("available", "unavailable", "unknown", "absent")
AUTHORITY_STATES = ("granted", "limited_without_grant", "unknown", "absent")


def _requirement_sources(
    intent: IntentContract, activation: ActivationPlan, kernels: list[KernelBinding]
) -> list[str]:
    return [f"intent:{intent.intent_id}", f"route:{activation.matched_route}"] + [
        f"kernel:{binding.source_ref}" for binding in kernels
    ]


def _compile_capabilities(
    intent: IntentContract,
    activation: ActivationPlan,
    kernels: list[KernelBinding],
    selected: Sequence[ContextItemIdentity],
) -> tuple[CapabilityContext, list[ContextUnknown]]:
    sources = _requirement_sources(intent, activation, kernels)
    required: list[CapabilityRequirement] = []

    def need(capability_id: str, reason: str) -> None:
        required.append(
            CapabilityRequirement(capability_id=capability_id, reason=reason, source_refs=sources)
        )

    mode = intent.objective.realization_mode.value
    if mode == "MUTATION":
        need("workspace_mutation", "realization mode MUTATION mutates the workspace")
    elif mode == "ARTIFACT":
        need("artifact_emission", "realization mode ARTIFACT returns files")
    if intent.objective.validation_required:
        need("validation_execution", "objective requires validation evidence")
    if activation.terminal_allowed:
        need("terminal_convergence", "activation plan reaches the terminal convergence gate")
    if (activation.architecture_materiality or {}).get("required"):
        need("architecture_review", "architecture materiality activates the Global Architect")

    required.sort(key=lambda item: (item.capability_id, item.requirement_id))

    facts = [item for item in selected if isinstance(item, CapabilityFact)]
    available = [fact for fact in facts if fact.state == "available"]
    unavailable = [fact for fact in facts if fact.state == "unavailable"]
    unknown_state = [fact for fact in facts if fact.state == "unknown"]

    available_ids = {fact.capability_id for fact in available}
    unavailable_ids = {fact.capability_id for fact in unavailable}
    unknown_ids = {fact.capability_id for fact in unknown_state}

    unknowns: list[ContextUnknown] = []
    for requirement in required:
        state = capability_disposition(
            requirement.capability_id, available_ids, unavailable_ids, unknown_ids
        )
        if state == "available":
            continue
        unknowns.append(
            ContextUnknown(
                semantic_key=requirement.capability_id,
                reason_code=UnknownReasonCode.UNSUPPORTED_CAPABILITY,
                materiality=(
                    UnknownMateriality.BLOCKING
                    if state == "unavailable"
                    else UnknownMateriality.NON_BLOCKING
                ),
                details={"capability_id": requirement.capability_id, "state": state},
            )
        )

    return (
        CapabilityContext(
            required=required,
            available=available,
            unavailable=unavailable,
            unknown=unknown_state,
        ),
        unknowns,
    )


def capability_disposition(
    capability_id: str,
    available_ids: set[str],
    unavailable_ids: set[str],
    unknown_ids: set[str],
) -> str:
    """The single explicit disposition of one required capability."""
    if capability_id in unavailable_ids:
        return "unavailable"
    if capability_id in available_ids:
        return "available"
    if capability_id in unknown_ids:
        return "unknown"
    return "absent"


def authority_disposition(
    authority_id: str,
    granted_ids: set[str],
    limited_ids: set[str],
    unknown_ids: set[str],
) -> str:
    """The single explicit disposition of one required authority.

    A grant wins over a limit: limits alongside a grant are a bounded grant,
    and they stay visible in ``AuthorityContext.limits``. A limit *without* a
    grant is a proven negative and blocks. The compiler default order is never
    consulted here — precedence is not permission (INV-CTX-022).
    """
    if authority_id in granted_ids:
        return "granted"
    if authority_id in limited_ids:
        return "limited_without_grant"
    if authority_id in unknown_ids:
        return "unknown"
    return "absent"


def _compile_authority(
    intent: IntentContract,
    scope: TaskScope,
    activation: ActivationPlan,
    kernels: list[KernelBinding],
    selected: Sequence[ContextItemIdentity],
    default_order: Sequence[str],
) -> tuple[AuthorityContext, list[ContextUnknown]]:
    sources = _requirement_sources(intent, activation, kernels)
    required: list[AuthorityRequirement] = []

    def need(authority_id: str, reason: str, action_scope: list[str]) -> None:
        required.append(
            AuthorityRequirement(
                authority_id=authority_id,
                subject_ref=None,
                action_scope=action_scope,
                reason=reason,
                source_refs=sources,
            )
        )

    if intent.objective.realization_mode.value == "MUTATION":
        need(
            "repository_write",
            "realization mode MUTATION writes to the workspace",
            list(scope.target_refs),
        )
    if intent.objective.delivery_required:
        need(
            "delivery",
            f"objective requires delivery in mode {intent.objective.delivery_mode.value}",
            [],
        )
    if (activation.architecture_materiality or {}).get("required"):
        need("architecture_decision", "architecture materiality requires a governed decision", [])

    required.sort(key=lambda item: (item.authority_id, item.requirement_id))

    facts = [item for item in selected if isinstance(item, AuthorityFact)]
    granted = [fact for fact in facts if fact.state == "granted"]
    limits = [fact for fact in facts if fact.state == "limit"]
    unknown_state = [fact for fact in facts if fact.state == "unknown"]

    granted_ids = {fact.authority_id for fact in granted}
    limited_ids = {fact.authority_id for fact in limits}
    unknown_ids = {fact.authority_id for fact in unknown_state}

    unknowns: list[ContextUnknown] = []
    for requirement in required:
        state = authority_disposition(
            requirement.authority_id, granted_ids, limited_ids, unknown_ids
        )
        if state == "granted":
            continue
        unknowns.append(
            ContextUnknown(
                semantic_key=requirement.authority_id,
                reason_code=UnknownReasonCode.MISSING_AUTHORITY,
                materiality=(
                    UnknownMateriality.BLOCKING
                    if state == "limited_without_grant"
                    else UnknownMateriality.NON_BLOCKING
                ),
                details={"authority_id": requirement.authority_id, "state": state},
            )
        )

    effective_order, source = _effective_authority_order(selected, granted, limits, default_order)

    return (
        AuthorityContext(
            required=required,
            granted=granted,
            limits=limits,
            unknown=unknown_state,
            effective_order=effective_order,
            effective_order_source=source,
        ),
        unknowns,
    )


def _effective_authority_order(
    selected: Sequence[ContextItemIdentity],
    granted: Sequence[AuthorityFact],
    limits: Sequence[AuthorityFact],
    default_order: Sequence[str],
) -> tuple[list[str], EffectiveAuthorityOrderSource]:
    """Governed precedence wins when proven; otherwise the labelled default.

    Caller hints never reach here (INV-CTX-022): only governed authority facts
    and selected applicable law can define an order. The returned default is a
    precedence fallback, never a grant.
    """
    ranked_facts = [fact for fact in [*granted, *limits] if fact.precedence is not None]
    if ranked_facts:
        ordered = sorted(ranked_facts, key=lambda fact: (fact.precedence or 0, fact.authority_id))
        return (
            list(dict.fromkeys(fact.authority_id for fact in ordered)),
            EffectiveAuthorityOrderSource.GOVERNED_CONTEXT,
        )
    ranked_law = [
        item for item in selected if isinstance(item, ApplicableLaw) and item.precedence is not None
    ]
    if ranked_law:
        ordered_law = sorted(ranked_law, key=lambda item: (item.precedence or 0, item.law_id))
        return (
            list(dict.fromkeys(item.law_id for item in ordered_law)),
            EffectiveAuthorityOrderSource.GOVERNED_CONTEXT,
        )
    return list(default_order), EffectiveAuthorityOrderSource.COMPILER_DEFAULT


__all__ = [
    "AUTHORITY_STATES",
    "CAPABILITY_STATES",
    "DISCOVERY_KINDS",
    "GLOBALLY_APPLICABLE_KINDS",
    "SUPERSESSION_KINDS",
    "ContextCompiler",
    "ContextDiscoveryCompiler",
    "GroupResolution",
    "SnapshotResolution",
    "apply_supersession",
    "authority_disposition",
    "capability_disposition",
    "matches_requirement",
    "preflight_snapshot",
    "resolve_snapshot",
]
