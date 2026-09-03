"""Canonical context artifact models (INV-CTX-003, INV-CTX-011).

These are the typed IR of the context-native compiler. Every model is a
fail-closed :class:`ArtifactModel`: unknown fields are rejected, serialization
is canonical, and digests are deterministic.

Four rules shape the whole module and are easy to break by accident:

1. ``CompiledTaskContext`` never carries its own digest (INV-CTX-027). The
   digest is computed from the finished artifact and carried *outside* it, by
   ``RuntimeBundle.digests()["context"]`` and the execution packet.
2. Semantic keys are defined by the item's *kind*, never by the caller
   (INV-CTX-011). Each kind declares a recipe; a disagreeing caller-supplied
   key fails closed.
3. Item identity is likewise compiler-owned (INV-CTX-011). ``item_id`` is
   derived from one canonical recipe over kind, semantic key, claim content,
   and source identity. A caller may omit it or supply the exact recipe value;
   anything else fails closed. Otherwise two byte-identical candidates could
   acquire different semantic identities purely from caller-chosen strings.
4. Snapshot candidates enter with empty ``selected_because``; only the
   compiler writes selection lineage, and only for admitted items.

No field in this module may be derived from a runtime clock, randomness, or
ambient version-control state (INV-CTX-032).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import field_validator, model_validator

from l9_cognitive_runtime.models.base import ArtifactModel
from l9_cognitive_runtime.models.canonical import canonical_json_bytes, sha256_digest

# Semantics version of the canonical context compiler. Bump this whenever the
# canonical compiled-context semantics change. It is deliberately explicit and
# installed-artifact safe: never derived from Git (INV-CTX-032).
CONTEXT_COMPILER_SEMANTICS_VERSION = "1.1.0"
CONTEXT_PLAN_SCHEMA_VERSION: Final = "l9.context-plan/v1"

# Finite input ceilings for an injected governed snapshot (INV-CTX-007). These
# bound the compiler's *input*, not only its output: without them a caller can
# make the compiler canonicalize, group, hash, and resolve an arbitrarily large
# snapshot before any output budget is ever consulted. Enforcement lives in the
# compiler preflight so that item-count rejection happens before any per-item
# resolution or hashing.
SNAPSHOT_MAX_ITEMS = 256
SNAPSHOT_MAX_BYTES = 1_048_576


# The snapshot's candidate buckets, in canonical order. Named once so the raw
# payload can be counted before it is typed (see ``payload_item_count``).
SNAPSHOT_BUCKETS = (
    "relevant_entities",
    "repository_state",
    "architecture_constraints",
    "applicable_law",
    "prior_decisions",
    "dependency_context",
    "evidence_refs",
    "memory_context",
    "capability_facts",
    "authority_facts",
)


def payload_item_count(payload: dict[str, Any]) -> int:
    """Count candidates in a *raw* snapshot payload, without typing any of them.

    Typing a candidate derives its identity, which hashes it. A host that types
    first would therefore hash every item of an oversized payload before the
    item ceiling could reject it, so the ceiling is applied to this count at the
    ingress boundary — before ``ContextSnapshot.from_mapping`` runs at all
    (INV-CTX-007).
    """
    return sum(
        len(value) for key in SNAPSHOT_BUCKETS if isinstance(value := payload.get(key), list)
    )


class ContextKind(StrEnum):
    RELEVANT_ENTITY = "relevant_entity"
    REPOSITORY_STATE = "repository_state"
    ARCHITECTURE_CONSTRAINT = "architecture_constraint"
    APPLICABLE_LAW = "applicable_law"
    PRIOR_DECISION = "prior_decision"
    DEPENDENCY_CONTEXT = "dependency_context"
    EVIDENCE_REF = "evidence_ref"
    MEMORY_CONTEXT = "memory_context"
    CAPABILITY_FACT = "capability_fact"
    AUTHORITY_FACT = "authority_fact"


class ContextScopeMode(StrEnum):
    SCOPED = "scoped"
    GLOBAL = "global"


class AuthorityLevel(StrEnum):
    GOVERNED_AUTHORITATIVE = "governed_authoritative"
    GOVERNED_VERIFIED = "governed_verified"
    INFORMATIVE = "informative"
    UNVERIFIED = "unverified"


# Canonical rank, strongest first. Enum declaration order must never be used as
# implicit precedence (INV-CTX-012) — this explicit map is the only ranking.
AUTHORITY_RANK: dict[AuthorityLevel, int] = {
    AuthorityLevel.GOVERNED_AUTHORITATIVE: 0,
    AuthorityLevel.GOVERNED_VERIFIED: 1,
    AuthorityLevel.INFORMATIVE: 2,
    AuthorityLevel.UNVERIFIED: 3,
}

GOVERNED_LEVELS = frozenset(
    {AuthorityLevel.GOVERNED_AUTHORITATIVE, AuthorityLevel.GOVERNED_VERIFIED}
)


class DecisionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class MissingPolicy(StrEnum):
    BLOCK = "BLOCK"
    PRESERVE_UNKNOWN = "PRESERVE_UNKNOWN"
    OPTIONAL = "OPTIONAL"


class CoverageMode(StrEnum):
    MINIMUM = "minimum"
    ALL_ELIGIBLE = "all_eligible"
    SEMANTIC_KEYS = "semantic_keys"


class UnknownMateriality(StrEnum):
    BLOCKING = "blocking"
    NON_BLOCKING = "non_blocking"


class UnknownReasonCode(StrEnum):
    AMBIGUOUS_SCOPE = "ambiguous_scope"
    MISSING_REQUIRED_CONTEXT = "missing_required_context"
    CONFLICTING_GOVERNED_CLAIMS = "conflicting_governed_claims"
    MISSING_REVISION = "missing_revision"
    INVALID_PROVENANCE = "invalid_provenance"
    BUDGET_INSUFFICIENT = "budget_insufficient"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    MISSING_AUTHORITY = "missing_authority"
    UNKNOWN_SUPERSESSION = "unknown_supersession"
    DANGLING_SUPERSESSION = "dangling_supersession"
    UNRESOLVED_FRESHNESS = "unresolved_freshness"


class EffectiveAuthorityOrderSource(StrEnum):
    GOVERNED_CONTEXT = "governed_context"
    COMPILER_DEFAULT = "compiler_default"


class FreshnessRequirement(StrEnum):
    EXACT_REVISION = "exact_revision"
    SNAPSHOT_BOUND = "snapshot_bound"
    ANY = "any"


# --------------------------------------------------------------------------
# Deterministic identity helpers (INV-CTX-011): full SHA-256, never truncated,
# never random, never clock-derived.
# --------------------------------------------------------------------------


_NON_EMPTY = "must be non-empty"


def derive_id(prefix: str, payload: Any) -> str:
    """Return ``<prefix>.sha256:<64 hex>`` over the canonical JSON payload."""
    return f"{prefix}.sha256:{sha256_digest(payload)}"


# Fields excluded from a candidate's *claim*: identity, provenance, authority,
# and scope say who asserts it and where it applies, not what is asserted.
# Excluding ``item_id`` is also what keeps identity derivation acyclic.
CLAIM_EXCLUDED_FIELDS = frozenset(
    {
        "item_id",
        "semantic_key",
        "context_kind",
        "authority_level",
        "source_ref",
        "scope_mode",
        "scope_refs",
        "selected_because",
    }
)

# Applicability is excluded from the *claim* but is part of *identity*. Two
# byte-identical statements that apply in different places are two different
# items, and collapsing them would let a claim eligible nowhere near the task
# stand in for one that is (INV-CTX-011).
APPLICABILITY_FIELDS = ("scope_mode", "scope_refs")


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(values))


def _assign(model: ArtifactModel, name: str, value: Any) -> None:
    """Write a compiler-derived identity field without re-entering validation."""
    model.__dict__[name] = value


class ContextSourceRef(ArtifactModel):
    """Where a context item came from, with an immutable coordinate when possible."""

    source_id: str
    source_kind: str
    locator: str
    immutable_coordinate: str | None = None
    content_digest: str | None = None

    @field_validator("source_id", "source_kind", "locator")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(_NON_EMPTY)
        return value

    @property
    def has_immutable_provenance(self) -> bool:
        return bool(self.immutable_coordinate) or bool(self.content_digest)

    def identity_payload(self) -> dict[str, Any]:
        """The stable source identity that participates in item identity."""
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "locator": self.locator,
            "immutable_coordinate": self.immutable_coordinate,
            "content_digest": self.content_digest,
        }


class ContextItemIdentity(ArtifactModel):
    """Identity, authority, scope, and selection lineage shared by every item.

    ``item_id`` is compiler-owned: leave it empty and it is derived; supply it
    and it must equal the derivation exactly (INV-CTX-011).
    """

    item_id: str = ""
    semantic_key: str
    context_kind: ContextKind
    authority_level: AuthorityLevel
    source_ref: ContextSourceRef
    scope_mode: ContextScopeMode
    scope_refs: list[str] = []
    selected_because: list[str] = []

    @field_validator("semantic_key")
    @classmethod
    def _non_empty_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(_NON_EMPTY)
        return value

    @field_validator("scope_refs", "selected_because")
    @classmethod
    def _canonical_refs(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value)

    def expected_semantic_key(self) -> str | None:
        """The kind's canonical semantic-key recipe, or None for the base type."""
        return None

    def claim_payload(self) -> dict[str, Any]:
        """What this item *asserts*, stripped of who asserts it and where."""
        data = self.to_canonical_dict()
        return {key: value for key, value in data.items() if key not in CLAIM_EXCLUDED_FIELDS}

    def applicability_payload(self) -> dict[str, Any]:
        """*Where* this item applies, separate from what it asserts.

        Built from ``APPLICABILITY_FIELDS`` rather than naming the fields
        again, so this and ``CLAIM_EXCLUDED_FIELDS`` cannot drift into
        disagreeing about which fields are applicability.
        """
        data = self.to_canonical_dict()
        return {field: data[field] for field in APPLICABILITY_FIELDS}

    def expected_item_id(self) -> str:
        """The one canonical item-identity recipe (INV-CTX-011).

        Applicability is a first-class component beside the claim. Without it
        two laws with the same text at different scopes share one identity, and
        deduplication then lets the wrong one carry the pair.
        """
        return derive_id(
            "ctxitem",
            {
                "context_kind": self.context_kind.value,
                "semantic_key": self.semantic_key,
                "claim": self.claim_payload(),
                "applicability": self.applicability_payload(),
                "source_identity": self.source_ref.identity_payload(),
            },
        )

    @model_validator(mode="after")
    def _validate_identity(self) -> ContextItemIdentity:
        if self.scope_mode is ContextScopeMode.SCOPED and not self.scope_refs:
            raise ValueError("scoped context item requires non-empty scope_refs")
        if self.scope_mode is ContextScopeMode.GLOBAL and self.scope_refs:
            raise ValueError("global context item requires empty scope_refs")
        expected_key = self.expected_semantic_key()
        if expected_key is not None and self.semantic_key != expected_key:
            raise ValueError(
                f"semantic_key must equal the {self.context_kind.value} recipe: {expected_key!r}"
            )
        if self.authority_level in GOVERNED_LEVELS and not self.source_ref.has_immutable_provenance:
            raise ValueError(
                "governed context item requires an immutable_coordinate or content_digest"
            )
        expected_id = self.expected_item_id()
        if not self.item_id:
            _assign(self, "item_id", expected_id)
        elif self.item_id != expected_id:
            raise ValueError(
                "item_id must equal the canonical ctxitem recipe over "
                "(context_kind, semantic_key, claim, source identity)"
            )
        return self

    def candidate_dict(self) -> dict[str, Any]:
        """Canonical form with selection lineage stripped."""
        data = self.to_canonical_dict()
        data["selected_because"] = []
        return data

    def candidate_digest(self) -> str:
        return sha256_digest(self.candidate_dict())

    @property
    def authority_rank(self) -> int:
        return AUTHORITY_RANK[self.authority_level]

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return (self.context_kind.value, self.semantic_key, self.item_id)


def canonical_cost(item: ContextItemIdentity) -> int:
    """Budget cost of a candidate: UTF-8 bytes of its canonical JSON.

    Selection lineage is excluded so that an item's cost is a property of the
    candidate itself and does not drift with how many requirements admitted it
    (INV-CTX-026).
    """
    return len(canonical_json_bytes(item.candidate_dict()))


class EntityContext(ContextItemIdentity):
    context_kind: Literal[ContextKind.RELEVANT_ENTITY] = ContextKind.RELEVANT_ENTITY
    entity_id: str
    entity_type: str
    relation_to_task: str

    def expected_semantic_key(self) -> str:
        return f"{self.entity_type}:{self.entity_id}"


class RepositoryState(ContextItemIdentity):
    """One repository fact claim. Never an opaque multi-fact bag (INV-CTX-010)."""

    context_kind: Literal[ContextKind.REPOSITORY_STATE] = ContextKind.REPOSITORY_STATE
    repository_id: str
    revision: str
    subject_ref: str
    fact_type: str
    value: Any = None

    @field_validator("revision", "subject_ref", "fact_type")
    @classmethod
    def _non_empty_fact(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(_NON_EMPTY)
        return value

    def expected_semantic_key(self) -> str:
        return f"{self.repository_id}:{self.subject_ref}:{self.fact_type}"


class GovernedConstraint(ContextItemIdentity):
    context_kind: Literal[ContextKind.ARCHITECTURE_CONSTRAINT] = ContextKind.ARCHITECTURE_CONSTRAINT
    constraint_id: str
    statement: str
    applies_because: list[str] = []
    evidence_refs: list[str] = []

    def expected_semantic_key(self) -> str:
        return self.constraint_id


class ApplicableLaw(ContextItemIdentity):
    context_kind: Literal[ContextKind.APPLICABLE_LAW] = ContextKind.APPLICABLE_LAW
    law_id: str
    statement: str
    applies_because: list[str] = []
    precedence: int | None = None
    supersedes_refs: list[str] = []

    @field_validator("precedence")
    @classmethod
    def _non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("precedence must be non-negative")
        return value

    def expected_semantic_key(self) -> str:
        return self.law_id


class PriorDecision(ContextItemIdentity):
    context_kind: Literal[ContextKind.PRIOR_DECISION] = ContextKind.PRIOR_DECISION
    decision_id: str
    status: DecisionStatus
    statement: str
    supersedes_refs: list[str] = []
    superseded_by_refs: list[str] = []

    def expected_semantic_key(self) -> str:
        return self.decision_id


class DependencyContext(ContextItemIdentity):
    context_kind: Literal[ContextKind.DEPENDENCY_CONTEXT] = ContextKind.DEPENDENCY_CONTEXT
    dependency_id: str
    relationship: str
    direction: str
    target_ref: str
    version_or_revision: str | None = None

    def expected_semantic_key(self) -> str:
        return f"{self.dependency_id}:{self.direction}:{self.relationship}:{self.target_ref}"


class EvidenceRef(ContextItemIdentity):
    """Evidence supports claims; it is not a universal truth layer (INV-CTX-018)."""

    context_kind: Literal[ContextKind.EVIDENCE_REF] = ContextKind.EVIDENCE_REF
    evidence_id: str
    evidence_type: str
    supports_semantic_keys: list[str] = []
    digest: str | None = None

    def expected_semantic_key(self) -> str:
        return self.evidence_id


class MemoryContext(ContextItemIdentity):
    """Enrichment only. Authority is ceilinged at ``informative`` (INV-CTX-019)."""

    context_kind: Literal[ContextKind.MEMORY_CONTEXT] = ContextKind.MEMORY_CONTEXT
    memory_id: str
    memory_kind: str
    content: Any = None
    relevance_reason: str = ""

    def expected_semantic_key(self) -> str:
        return self.memory_id

    @model_validator(mode="after")
    def _authority_ceiling(self) -> MemoryContext:
        if self.authority_level in GOVERNED_LEVELS:
            raise ValueError("memory_context authority is ceilinged at informative")
        return self


class CapabilityFact(ContextItemIdentity):
    """A proven capability state. A snapshot may never declare ``required``."""

    context_kind: Literal[ContextKind.CAPABILITY_FACT] = ContextKind.CAPABILITY_FACT
    capability_id: str
    state: Literal["available", "unavailable", "unknown"]
    evidence_refs: list[str] = []

    def expected_semantic_key(self) -> str:
        return self.capability_id


class AuthorityFact(ContextItemIdentity):
    """A proven authority grant/limit. A snapshot may never declare ``required``."""

    context_kind: Literal[ContextKind.AUTHORITY_FACT] = ContextKind.AUTHORITY_FACT
    authority_id: str
    state: Literal["granted", "limit", "unknown"]
    subject_ref: str | None = None
    action_scope: list[str] = []
    precedence: int | None = None

    @field_validator("action_scope")
    @classmethod
    def _canonical_actions(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value)

    @field_validator("precedence")
    @classmethod
    def _non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("precedence must be non-negative")
        return value

    def expected_semantic_key(self) -> str:
        return authority_semantic_key(self.authority_id, self.subject_ref, self.action_scope)


def authority_semantic_key(
    authority_id: str, subject_ref: str | None, action_scope: list[str]
) -> str:
    """Canonical authority semantic key: id + subject + canonical action scope."""
    return f"{authority_id}:{subject_ref or ''}:{','.join(_sorted_unique(action_scope))}"


# --------------------------------------------------------------------------
# Authority coverage (INV-CTX-022).
#
# An authority requirement names three things — the authority, the subject it
# is needed over, and the actions it must permit. Matching on ``authority_id``
# alone would let a grant for one subject or one action close a gap it never
# covers, which is the precise shape of a permission nobody proved.
#
# Two directions are needed and they are not the same relation:
#
# * a **grant** must *contain* the requirement — everything required is
#   permitted, so an absent field on the grant reads as unrestricted;
# * a **limit** need only *intersect* the requirement — a limit narrower than
#   what is required still bears on it, so an absent field on either side
#   cannot be assumed disjoint.
#
# Both fail closed: an unstated subject on a grant does not silently become
# the required subject, and an unstated field on a limit does not silently
# make the limit irrelevant.
# --------------------------------------------------------------------------


def _grant_subject_covers(grant_subject: str | None, required_subject: str | None) -> bool:
    """A grant naming no subject is unrestricted; otherwise it must match."""
    if grant_subject is None:
        return True
    return grant_subject == required_subject


def _grant_actions_cover(grant_actions: list[str], required_actions: list[str]) -> bool:
    """A grant naming no actions is unrestricted; otherwise it must contain."""
    if not grant_actions:
        return True
    return set(required_actions) <= set(grant_actions)


def _limit_subject_bears(limit_subject: str | None, required_subject: str | None) -> bool:
    """An unstated subject on either side cannot be proven disjoint."""
    if limit_subject is None or required_subject is None:
        return True
    return limit_subject == required_subject


def _limit_actions_bear(limit_actions: list[str], required_actions: list[str]) -> bool:
    """An unstated action scope on either side cannot be proven disjoint."""
    if not limit_actions or not required_actions:
        return True
    return bool(set(limit_actions) & set(required_actions))


def grant_covers_requirement(fact: AuthorityFact, requirement: AuthorityRequirement) -> bool:
    """True when this granted fact covers everything the requirement needs."""
    return (
        fact.authority_id == requirement.authority_id
        and _grant_subject_covers(fact.subject_ref, requirement.subject_ref)
        and _grant_actions_cover(fact.action_scope, requirement.action_scope)
    )


def limit_bears_on_requirement(fact: AuthorityFact, requirement: AuthorityRequirement) -> bool:
    """True when this limit fact bears on what the requirement asks for."""
    return (
        fact.authority_id == requirement.authority_id
        and _limit_subject_bears(fact.subject_ref, requirement.subject_ref)
        and _limit_actions_bear(fact.action_scope, requirement.action_scope)
    )


class ContextUnknown(ArtifactModel):
    """A stable, reason-coded unknown. Identity never depends on prose."""

    unknown_id: str = ""
    requirement_ref: str | None = None
    semantic_key: str | None = None
    reason_code: UnknownReasonCode
    details: dict[str, Any] = {}
    materiality: UnknownMateriality
    source_refs: list[ContextSourceRef] = []

    def expected_unknown_id(self) -> str:
        """The one canonical unknown-identity recipe (INV-CTX-024)."""
        return derive_id(
            "ctxunk",
            {
                "requirement_ref": self.requirement_ref,
                "semantic_key": self.semantic_key,
                "reason_code": self.reason_code.value,
                "details": self.details,
            },
        )

    @model_validator(mode="after")
    def _derive_identity(self) -> ContextUnknown:
        expected = self.expected_unknown_id()
        if not self.unknown_id:
            _assign(self, "unknown_id", expected)
        elif self.unknown_id != expected:
            raise ValueError("unknown_id must be the deterministic ctxunk recipe")
        return self


class TaskScope(ArtifactModel):
    scope_id: str = ""
    mission: str
    task_type: str
    target_refs: list[str] = []
    in_scope_refs: list[str] = []
    excluded_refs: list[str] = []
    requested_outputs: list[str] = []
    constraints: list[str] = []
    unresolved_unknowns: list[ContextUnknown] = []

    @field_validator(
        "target_refs", "in_scope_refs", "excluded_refs", "requested_outputs", "constraints"
    )
    @classmethod
    def _canonical_lists(cls, value: list[str]) -> list[str]:
        return _sorted_unique([item for item in value if item.strip()])

    @model_validator(mode="after")
    def _derive_identity(self) -> TaskScope:
        payload = {
            "mission": self.mission,
            "task_type": self.task_type,
            "target_refs": self.target_refs,
            "in_scope_refs": self.in_scope_refs,
            "excluded_refs": self.excluded_refs,
            "requested_outputs": self.requested_outputs,
            "constraints": self.constraints,
            "unresolved_unknowns": [u.to_canonical_dict() for u in self.unresolved_unknowns],
        }
        expected = derive_id("scope", payload)
        if not self.scope_id:
            _assign(self, "scope_id", expected)
        elif self.scope_id != expected:
            raise ValueError("scope_id must be the deterministic scope recipe")
        return self

    @property
    def eligible_refs(self) -> frozenset[str]:
        """Every reference a scoped context item may legally intersect.

        Exclusions are real: an excluded reference is removed from the eligible
        set, so it can never select scoped context (INV-CTX-006). Matching is
        exact — no prefix, glob, or ancestry semantics are invented from plain
        strings.
        """
        included = frozenset(self.target_refs) | frozenset(self.in_scope_refs)
        return included - frozenset(self.excluded_refs)

    @property
    def scope_conflicts(self) -> tuple[str, ...]:
        """References that are simultaneously included and excluded."""
        included = frozenset(self.target_refs) | frozenset(self.in_scope_refs)
        return tuple(sorted(included & frozenset(self.excluded_refs)))


class ContextRequirement(ArtifactModel):
    """One explicitly declared context need (INV-CTX-008)."""

    requirement_id: str = ""
    context_kind: ContextKind
    reason: str
    required: bool
    scope_mode: ContextScopeMode
    scope_refs: list[str] = []
    freshness_requirement: FreshnessRequirement
    coordinate_constraint: str | None = None
    minimum_authority: AuthorityLevel
    priority: int
    coverage_mode: CoverageMode
    min_items: int
    required_semantic_keys: list[str] = []
    max_items: int | None = None
    max_bytes: int | None = None
    missing_policy: MissingPolicy
    # Provenance of a requirement that a selected kernel demanded (INV-CTX-020).
    # Empty for the compiler's own baseline requirements.
    kernel_need_refs: list[str] = []

    @field_validator("reason")
    @classmethod
    def _non_empty_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be non-empty")
        return value

    @field_validator("scope_refs", "required_semantic_keys", "kernel_need_refs")
    @classmethod
    def _canonical_lists(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value)

    @model_validator(mode="after")
    def _validate_requirement(self) -> ContextRequirement:
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.min_items < 0:
            raise ValueError("min_items must be non-negative")
        if self.scope_mode is ContextScopeMode.SCOPED and not self.scope_refs:
            raise ValueError("scoped requirement requires non-empty scope_refs")
        if self.scope_mode is ContextScopeMode.GLOBAL and self.scope_refs:
            raise ValueError("global requirement requires empty scope_refs")
        if self.required and self.min_items < 1:
            raise ValueError("required requirement needs min_items >= 1")
        if self.max_items is not None:
            if self.max_items < 1:
                raise ValueError("max_items must be positive")
            if self.max_items < self.min_items:
                raise ValueError("max_items must be at least min_items")
        if self.max_bytes is not None and self.max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        if self.max_items is None and self.max_bytes is None:
            raise ValueError("requirement needs at least one of max_items or max_bytes")
        if (
            self.coverage_mode in {CoverageMode.MINIMUM, CoverageMode.ALL_ELIGIBLE}
            and self.required_semantic_keys
        ):
            raise ValueError(f"{self.coverage_mode.value} coverage forbids required_semantic_keys")
        if self.coverage_mode is CoverageMode.SEMANTIC_KEYS:
            if not self.required_semantic_keys:
                raise ValueError("semantic_keys coverage requires required_semantic_keys")
            if self.min_items < len(self.required_semantic_keys):
                raise ValueError(
                    "semantic_keys coverage requires min_items >= number of required keys"
                )
        if (
            self.freshness_requirement is FreshnessRequirement.EXACT_REVISION
            and not (self.coordinate_constraint or "").strip()
        ):
            raise ValueError("exact_revision freshness requires a coordinate_constraint")
        if self.required and self.missing_policy is MissingPolicy.OPTIONAL:
            raise ValueError("required requirement cannot use the OPTIONAL missing policy")
        expected = derive_id("ctxreq", self._identity_payload())
        if not self.requirement_id:
            _assign(self, "requirement_id", expected)
        elif self.requirement_id != expected:
            raise ValueError("requirement_id must be the deterministic ctxreq recipe")
        return self

    def _identity_payload(self) -> dict[str, Any]:
        payload = self.to_canonical_dict()
        payload.pop("requirement_id", None)
        return payload

    @property
    def order_key(self) -> tuple[int, str, str]:
        return (self.priority, self.context_kind.value, self.requirement_id)


class ContextBudget(ArtifactModel):
    max_total_items: int
    max_total_bytes: int

    @model_validator(mode="after")
    def _positive(self) -> ContextBudget:
        if self.max_total_items < 1 or self.max_total_bytes < 1:
            raise ValueError("global budget bounds must be positive")
        return self


class ContextRequirementPlan(ArtifactModel):
    plan_id: str = ""
    task_scope_digest: str
    matched_route: str
    global_budget: ContextBudget
    requirements: list[ContextRequirement] = []

    @model_validator(mode="after")
    def _canonical_plan(self) -> ContextRequirementPlan:
        ordered = sorted(self.requirements, key=lambda req: req.order_key)
        if [req.requirement_id for req in ordered] != [
            req.requirement_id for req in self.requirements
        ]:
            _assign(self, "requirements", ordered)
        ids = [req.requirement_id for req in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate requirement_id in plan")
        payload = {
            "task_scope_digest": self.task_scope_digest,
            "matched_route": self.matched_route,
            "global_budget": self.global_budget.to_canonical_dict(),
            "requirements": [req.to_canonical_dict() for req in ordered],
        }
        expected = derive_id("ctxplan", payload)
        if not self.plan_id:
            _assign(self, "plan_id", expected)
        elif self.plan_id != expected:
            raise ValueError("plan_id must be the deterministic ctxplan recipe")
        return self


class ContextPlan(ArtifactModel):
    """Public demand contract between cognitive planning and outer-host acquisition.

    The plan contains no acquired context. It binds the task scope, bounded
    discovery projection, selected kernel identities, requirement set, and the
    verified semantic sources that produced them. An outer host may fulfill the
    requirements, but final compilation must recompute this identity before it
    can trust a supplied snapshot (INV-CTX-045/046).
    """

    schema_version: Literal["l9.context-plan/v1"] = CONTEXT_PLAN_SCHEMA_VERSION
    context_plan_id: str = ""
    task_scope: TaskScope
    discovery: DiscoveryContext
    requirement_plan: ContextRequirementPlan
    active_kernel_digests: dict[str, str]
    pack_manifest_digest: str
    routing_rules_digest: str
    pipeline_digest: str
    compiler_identity: CompilerIdentity

    @model_validator(mode="after")
    def _derive_identity(self) -> ContextPlan:
        scope_digest = self.task_scope.sha256()
        if self.discovery.task_scope_digest != scope_digest:
            raise ValueError("context plan discovery does not bind the task scope")
        if self.requirement_plan.task_scope_digest != scope_digest:
            raise ValueError("context requirement plan does not bind the task scope")
        if not self.requirement_plan.matched_route.strip():
            raise ValueError("context plan requires a matched route")
        payload = self.to_canonical_dict()
        payload.pop("context_plan_id", None)
        expected = derive_id("context-plan", payload)
        if not self.context_plan_id:
            _assign(self, "context_plan_id", expected)
        elif self.context_plan_id != expected:
            raise ValueError("context_plan_id must be the deterministic context-plan recipe")
        return self


class CapabilityRequirement(ArtifactModel):
    """Compiler-derived. A ``ContextSnapshot`` can never produce one."""

    requirement_id: str = ""
    capability_id: str
    reason: str
    source_refs: list[str] = []

    @field_validator("source_refs")
    @classmethod
    def _canonical_refs(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value)

    @model_validator(mode="after")
    def _derive_identity(self) -> CapabilityRequirement:
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")
        expected = derive_id(
            "capreq",
            {
                "capability_id": self.capability_id,
                "reason": self.reason,
                "source_refs": self.source_refs,
            },
        )
        if not self.requirement_id:
            _assign(self, "requirement_id", expected)
        elif self.requirement_id != expected:
            raise ValueError("requirement_id must be the deterministic capreq recipe")
        return self

    @property
    def semantic_key(self) -> str:
        return self.capability_id


class AuthorityRequirement(ArtifactModel):
    """Compiler-derived. A ``ContextSnapshot`` can never produce one."""

    requirement_id: str = ""
    authority_id: str
    subject_ref: str | None = None
    action_scope: list[str] = []
    reason: str
    source_refs: list[str] = []

    @field_validator("action_scope", "source_refs")
    @classmethod
    def _canonical_refs(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value)

    @model_validator(mode="after")
    def _derive_identity(self) -> AuthorityRequirement:
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")
        expected = derive_id(
            "authreq",
            {
                "authority_id": self.authority_id,
                "subject_ref": self.subject_ref,
                "action_scope": self.action_scope,
                "reason": self.reason,
                "source_refs": self.source_refs,
            },
        )
        if not self.requirement_id:
            _assign(self, "requirement_id", expected)
        elif self.requirement_id != expected:
            raise ValueError("requirement_id must be the deterministic authreq recipe")
        return self

    @property
    def semantic_key(self) -> str:
        return authority_semantic_key(self.authority_id, self.subject_ref, self.action_scope)


class CapabilityContext(ArtifactModel):
    """Required / available / unavailable / unknown stay distinct (INV-CTX-021)."""

    required: list[CapabilityRequirement] = []
    available: list[CapabilityFact] = []
    unavailable: list[CapabilityFact] = []
    unknown: list[CapabilityFact] = []


class AuthorityContext(ArtifactModel):
    """Required / granted / limits / unknown stay distinct (INV-CTX-022)."""

    required: list[AuthorityRequirement] = []
    granted: list[AuthorityFact] = []
    limits: list[AuthorityFact] = []
    unknown: list[AuthorityFact] = []
    effective_order: list[str] = []
    effective_order_source: EffectiveAuthorityOrderSource


class DiscoveryContext(ArtifactModel):
    """Bounded projection #1: only what routing and materiality need."""

    task_scope_digest: str
    routing_fact_refs: list[str] = []
    architecture_signal_refs: list[str] = []
    unresolved_unknowns: list[ContextUnknown] = []
    selected_item_digests: dict[str, str] = {}

    @field_validator("routing_fact_refs", "architecture_signal_refs")
    @classmethod
    def _canonical_refs(cls, value: list[str]) -> list[str]:
        return _sorted_unique(value)


class CompilerIdentity(ArtifactModel):
    """Installed-artifact-safe compiler semantics identity (INV-CTX-032)."""

    package_version: str
    semantics_version: str

    @field_validator("package_version", "semantics_version")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(_NON_EMPTY)
        return value


class ContextProvenance(ArtifactModel):
    """Reproduction identity for the compiled context.

    ``context_digest`` is deliberately absent: it is computed *from* the
    finished ``CompiledTaskContext`` and carried outside it (INV-CTX-027). So
    is any whole-snapshot digest, which would let irrelevant unselected input
    perturb semantic identity (INV-CTX-028).
    """

    task_scope_digest: str
    discovery_digest: str
    context_requirements_digest: str
    discovery_item_digests: dict[str, str] = {}
    selected_item_digests: dict[str, str] = {}
    kernel_digests: dict[str, str] = {}
    compiler_identity: CompilerIdentity


class ContextSnapshot(ArtifactModel):
    """Immutable governed candidates supplied by the outer host (INV-CTX-007).

    This is a separate compiler input, never a ``CompileRequest`` field: raw
    caller hints must never be promoted into governed truth (INV-CTX-006).
    """

    relevant_entities: list[EntityContext] = []
    repository_state: list[RepositoryState] = []
    architecture_constraints: list[GovernedConstraint] = []
    applicable_law: list[ApplicableLaw] = []
    prior_decisions: list[PriorDecision] = []
    dependency_context: list[DependencyContext] = []
    evidence_refs: list[EvidenceRef] = []
    memory_context: list[MemoryContext] = []
    capability_facts: list[CapabilityFact] = []
    authority_facts: list[AuthorityFact] = []

    @classmethod
    def empty(cls) -> ContextSnapshot:
        """The governed-empty snapshot: what ``context_snapshot=None`` means."""
        return cls()

    @model_validator(mode="after")
    def _candidates_carry_no_selection(self) -> ContextSnapshot:
        for item in self.all_items():
            if item.selected_because:
                raise ValueError(
                    "snapshot candidate must not supply selected_because; "
                    "selection lineage is compiler-generated"
                )
        return self

    def _buckets(self) -> tuple[list[Any], ...]:
        return (
            self.relevant_entities,
            self.repository_state,
            self.architecture_constraints,
            self.applicable_law,
            self.prior_decisions,
            self.dependency_context,
            self.evidence_refs,
            self.memory_context,
            self.capability_facts,
            self.authority_facts,
        )

    def item_count(self) -> int:
        """Total candidate count, computed without touching any item.

        The preflight rejects an oversized snapshot from this alone, before any
        per-item resolution or hashing happens (INV-CTX-007).
        """
        return sum(len(bucket) for bucket in self._buckets())

    def canonical_byte_size(self) -> int:
        """Deterministic canonical UTF-8 byte size of the whole snapshot."""
        return len(canonical_json_bytes(self.to_canonical_dict()))

    def all_items(self) -> list[ContextItemIdentity]:
        items: list[ContextItemIdentity] = []
        for bucket in self._buckets():
            items.extend(bucket)
        return items

    def audit_digest(self) -> str:
        """Non-semantic whole-snapshot digest for audit only.

        Never participates in ``CompiledTaskContext`` or bundle semantic
        identity (INV-CTX-028).
        """
        return self.sha256()


class CompiledTaskContext(ArtifactModel):
    """The canonical context IR (INV-CTX-003). Carries no digest of itself."""

    task_scope: TaskScope
    relevant_entities: list[EntityContext] = []
    repository_state: list[RepositoryState] = []
    architecture_constraints: list[GovernedConstraint] = []
    applicable_law: list[ApplicableLaw] = []
    prior_decisions: list[PriorDecision] = []
    dependency_context: list[DependencyContext] = []
    evidence_refs: list[EvidenceRef] = []
    memory_context: list[MemoryContext] = []
    selected_kernels: list[dict[str, Any]] = []
    capabilities: CapabilityContext
    authority: AuthorityContext
    unresolved_unknowns: list[ContextUnknown] = []
    provenance: ContextProvenance

    def selected_items(self) -> list[ContextItemIdentity]:
        items: list[ContextItemIdentity] = []
        for bucket in (
            self.relevant_entities,
            self.repository_state,
            self.architecture_constraints,
            self.applicable_law,
            self.prior_decisions,
            self.dependency_context,
            self.evidence_refs,
            self.memory_context,
        ):
            items.extend(bucket)
        items.extend(self.capabilities.available)
        items.extend(self.capabilities.unavailable)
        items.extend(self.capabilities.unknown)
        items.extend(self.authority.granted)
        items.extend(self.authority.limits)
        items.extend(self.authority.unknown)
        return items


__all__ = [
    "AUTHORITY_RANK",
    "CLAIM_EXCLUDED_FIELDS",
    "CONTEXT_COMPILER_SEMANTICS_VERSION",
    "CONTEXT_PLAN_SCHEMA_VERSION",
    "GOVERNED_LEVELS",
    "SNAPSHOT_BUCKETS",
    "SNAPSHOT_MAX_BYTES",
    "SNAPSHOT_MAX_ITEMS",
    "ApplicableLaw",
    "AuthorityContext",
    "AuthorityFact",
    "AuthorityLevel",
    "AuthorityRequirement",
    "CapabilityContext",
    "CapabilityFact",
    "CapabilityRequirement",
    "CompiledTaskContext",
    "CompilerIdentity",
    "ContextBudget",
    "ContextItemIdentity",
    "ContextPlan",
    "ContextKind",
    "ContextProvenance",
    "ContextRequirement",
    "ContextRequirementPlan",
    "ContextScopeMode",
    "ContextSnapshot",
    "ContextSourceRef",
    "ContextUnknown",
    "CoverageMode",
    "DecisionStatus",
    "DependencyContext",
    "DiscoveryContext",
    "EffectiveAuthorityOrderSource",
    "EntityContext",
    "EvidenceRef",
    "FreshnessRequirement",
    "GovernedConstraint",
    "MemoryContext",
    "MissingPolicy",
    "PriorDecision",
    "RepositoryState",
    "TaskScope",
    "UnknownMateriality",
    "UnknownReasonCode",
    "authority_semantic_key",
    "canonical_cost",
    "derive_id",
    "payload_item_count",
]
