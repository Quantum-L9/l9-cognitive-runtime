# L9 Cognitive Runtime Invariants

Status: CANONICAL ARCHITECTURE LAW  
Scope: `Quantum-L9/l9-cognitive-runtime`  
Primary concern: deterministic task-scoped cognitive compilation

## 1. Repository identity

The L9 Cognitive Runtime is the deterministic task-to-cognitive-execution compiler. It converts a task plus governed source context into the minimum sufficient, provenance-backed cognitive context and execution packet required to perform that task correctly.

The repository does not own task execution, persistent world state, semantic memory storage, observability infrastructure, transport routing, provider infrastructure, or agent-host lifecycle management.

## 2. Primary invariants

### INV-CTX-001: Task-scoped compilation is the primary concern

Every live feature MUST materially strengthen task interpretation, task scope derivation, context requirement derivation, governed context selection and reduction, kernel/cognitive-capability selection, obligation derivation, execution/validation/handoff compilation, execution-packet compilation, or deterministic adapter projection.

A feature whose primary purpose does not strengthen that chain belongs outside this repository unless it is strictly necessary to expose, package, or validate the compiler.

### INV-CTX-002: One live compilation spine

There MUST be exactly one authoritative fresh-mission semantic spine. Compatibility wrappers MAY delegate to it but MUST NOT implement a second compiler.

Canonical dependency direction:

```text
CompileRequest + ContextSnapshot
  -> ObjectiveDeriver
  -> TaskScopeCompiler
  -> ContextDiscoveryCompiler
  -> ActivationPlanner
  -> KernelResolver
  -> ContextRequirementPlanner
  -> ContextCompiler
  -> CompiledTaskContext
  -> ContextClosureValidator
  -> ObligationDeriver
  -> ExecutionContractCompiler
  -> ValidationContractCompiler
  -> HandoffContractCompiler
  -> ExecutionGraphCompiler
  -> BundleSemanticValidator
  -> ExecutionPacket
  -> AdapterRenderer
```

Exact class names MAY evolve. Ownership and dependency direction MUST NOT.

### INV-CTX-003: CompiledTaskContext is a first-class canonical IR

Every successful fresh-mission compile MUST produce exactly one canonical `CompiledTaskContext` containing:

```text
CompiledTaskContext
{
    task_scope
    relevant_entities
    repository_state
    architecture_constraints
    applicable_law
    prior_decisions
    dependency_context
    evidence_refs
    memory_context
    selected_kernels
    capabilities
    authority
    unresolved_unknowns
    provenance
}
```

It MUST use the repository's fail-closed artifact-model conventions, forbid unknown fields, serialize canonically, and have a deterministic digest.

### INV-CTX-004: Minimum sufficient context

The compiler MUST select the minimum sufficient governed context for the task. It MUST NOT maximize ingestion, copy whole repositories by default, dump all policy, load all memory, or treat larger context as better context.

Every selected context item MUST bind through stable IDs to at least one task-scope element, `ContextRequirement`, or selected-kernel requirement. Downstream obligations MAY reference the closed context, but context selection MUST NOT depend on obligations that have not yet been derived.

### INV-CTX-005: Context compilation is bounded and non-agentic

Context compilation MUST be deterministic and bounded. Open-ended loops such as "search until satisfied", recursive autonomous browsing, or LLM reasoning inside the canonical compiler are forbidden.

The foundation uses exactly two bounded semantic projections over an immutable injected snapshot:

1. discovery projection: enough verified context to scope and route;
2. requirement-bound projection: the context explicitly required after routing and kernel selection.

External hosts MAY later use a planning API to acquire data between phases, but acquisition remains outside the semantic compiler.

### INV-CTX-006: Raw caller context is not authority

`CompileRequest.source_context` MAY provide target references, caller hints, or seed material. It MUST NOT directly establish repository truth, architecture truth, governing law, authority, capability availability, decision status, or evidence validity.

Any hint that affects execution semantics MUST first resolve to a typed, provenance-backed governed context item.

### INV-CTX-007: Governed context is a separate compiler input

Authoritative or evidence-bearing context MUST enter compilation as a typed `ContextSnapshot` or equivalent governed input separate from `CompileRequest.source_context`.

The service and compiler MAY accept `context_snapshot=None` for backward compatibility, which is equivalent to an empty governed snapshot. They MUST NOT silently promote caller hints into the governed snapshot.

### INV-CTX-008: Context requirements precede detailed selection

Detailed context selection MUST be driven by an explicit typed `ContextRequirementPlan`.

Each requirement MUST define stable identity, context kind, reason, required/optional status, explicit scope mode and selectors, freshness requirement plus exact coordinate constraint when applicable, minimum authority level, deterministic priority, coverage mode, minimum coverage (`min_items`), required semantic keys when applicable, item budget, byte budget, and missing-data policy. Coverage mode MUST distinguish at least `minimum`, `all_eligible`, and `semantic_keys`. Requirement satisfaction MUST be mechanically decidable from those fields and any kind-specific rule.

Only the bounded discovery projection is exempt from requiring the final requirement plan.

### INV-CTX-009: Context-source infrastructure stays outside the compiler

The compiler MAY define source contracts and consume immutable snapshots. It MUST NOT own GitHub crawling, Graphiti persistence, vector/database clients, network discovery, transport routing, or organization-wide state services.

This prohibition does NOT forbid immutable reads of the verified runtime pack already required by the live compiler, including routing rules, pipeline definitions, kernels, schemas, and other manifest-bound semantic sources.

### INV-CTX-010: Repository state is revision-bound

Repository facts that affect compilation MUST identify repository identity plus an exact commit, tree, content digest, or equivalent immutable coordinate.

Unbound branch names, ambient working-directory observations, or unversioned prose MUST NOT become canonical repository truth.

### INV-CTX-011: Every material context item has stable identity and provenance

Every material context item MUST have:

- stable item identity;
- context kind;
- a deterministic semantic key derived or validated from that kind's canonical recipe;
- source reference;
- explicit `scoped` or `global` scope mode;
- immutable source coordinate or content digest where the source permits it;
- authority/truth classification appropriate to its domain;
- compiler-generated relevance binding when selected.

Snapshot candidates MUST enter with empty selection bindings. The compiler MUST populate `selected_because` only after selection. Repository-state items MUST represent one semantic claim each rather than an opaque multi-fact map. Random identifiers and compiler-generated timestamps MUST NOT participate in canonical semantic output.

### INV-CTX-012: Ordering and deduplication are deterministic

Input list order MUST NOT change compiled semantic output.

Candidates MUST be canonically normalized and sorted before selection. Semantically identical duplicate candidates MUST collapse deterministically. Authority rank, immutable coordinate, content digest, stable semantic key, and stable item ID MUST provide explicit canonical tie-breaking. Enum declaration order and input list position MUST NOT provide hidden precedence.

### INV-CTX-013: Conflicts are resolved by semantic key, not by context-bag order

Conflicts exist only between claims of the same context kind that address the same deterministic semantic key. Every context kind MUST define its semantic-key recipe and domain precedence rule.

When two same-key claims differ:

- a stronger governed authority MAY supersede a weaker claim only when that context kind's domain rule permits it;
- applicable law resolves explicit supersession and declared law precedence before generic authority rank;
- prior decisions resolve explicit supersession status before generic authority rank;
- memory and caller hints MUST never override governed authoritative facts;
- equal-authority contradictory governed claims MUST NOT be arbitrarily chosen and MUST become an explicit `ContextUnknown` or governed block according to the requirement's missing/conflict policy.

Evidence supports claims; evidence itself is not a generic truth-precedence layer.

### INV-CTX-014: Architecture constraints require evidence

Architecture materiality MAY consume mission text as a candidate signal, but external architecture facts MUST be established by typed discovery facts with provenance.

Kernel file presence and raw `source_context.context_signals` MUST NOT directly prove architecture materiality.

### INV-CTX-015: Applicable law is selected, not dumped

The compiler MUST include only law, policy, contracts, and governance rules applicable to the compiled task scope.

Each law item MUST preserve identity, applicability reason, source provenance, and authority/precedence relationship when known.

### INV-CTX-016: Prior decisions preserve status and supersession

A prior decision MUST distinguish at least `active`, `superseded`, and `unknown` status.

Superseded decisions MUST NOT silently remain active. Material unknown supersession MUST remain visible.

### INV-CTX-017: Dependency context is task-relevant

Dependency context MUST include only upstream, downstream, package, repository, API, schema, or runtime seams materially relevant to task scope or selected kernels.

Dependency facts require source provenance. Textual proximity is not dependency authority.

### INV-CTX-018: Evidence is addressable and non-fabricated

Evidence references MUST have stable identity and an addressable locator. They SHOULD carry a digest or immutable coordinate when the source permits it.

Successful parsing, successful retrieval, or file existence MUST NOT be transformed into proof of correctness.

### INV-CTX-019: Memory is enrichment, never operational truth

`memory_context` MAY provide associative recall, historical context, experience, and semantic relationships.

Memory MUST NOT redefine current repository state, governing law, authority, exact dependencies, or validated evidence. Material conflicts preserve governed truth and record the conflict when useful.

### INV-CTX-020: Kernel selection is part of compiled context

Every selected kernel MUST use the existing fail-closed `KernelBinding` identity, source reference, digest, and typed output model.

`CompiledTaskContext.selected_kernels` MUST exactly equal the bindings consumed by downstream obligation and execution compilation.

### INV-CTX-021: Capability requirement and availability are distinct

The compiler MUST separately represent capabilities that are required, proven available, proven unavailable, and unknown. Required capability is compiler-derived from task/objective/route/kernel semantics; source snapshots MAY prove availability or unavailability but MUST NOT declare the task's required capabilities.

Required MUST NOT imply available.

### INV-CTX-022: Authority requirement, grant, limit, and effective order are distinct

The compiler MUST separately represent required authority, proven grants, explicit limits, and unknown authority. Required authority is compiler-derived from task/objective/route/kernel semantics; source snapshots MAY prove grants, limits, or unknown state but MUST NOT declare what authority the task requires.

Context-specific governing authority order MUST take precedence when proven. For backward compatibility, the current compiler authority order MAY remain as an explicit `compiler_default` only when no more specific governed order is available. The output MUST identify whether its effective order came from governed context or the compiler default.

Caller hints MUST NOT define effective authority order.

### INV-CTX-023: Missing data has an explicit policy

Every required `ContextRequirement` MUST define one missing-data policy:

- `BLOCK`: absence or unresolved equal-authority conflict makes compilation fail closed;
- `PRESERVE_UNKNOWN`: compilation may continue only with a stable `ContextUnknown` bound to that requirement;
- `OPTIONAL`: absence does not block and does not require a semantic Unknown.

The compiler MUST NOT decide missing-data behavior ad hoc after selection.

### INV-CTX-024: Unknowns are conserved

Material unresolved unknowns MUST remain explicit through `CompiledTaskContext`, obligation derivation, handoff, validation, and the execution packet until legally disposed. Unknown identity MUST be derived from stable reason codes and canonical details, not human prose, random IDs, or timestamps.

Missing information MUST NOT be replaced by semantics-changing defaults.

### INV-CTX-025: Context closure precedes execution semantics

A context-closure validator MUST run before downstream execution semantics are considered valid.

At minimum it MUST verify required requirement disposition, provenance, relevance bindings, same-key conflict disposition, memory non-authority, exact kernel equality, capability/authority gaps, budget compliance, and unknown conservation.

### INV-CTX-026: Context budgets have canonical measurement and reduction

The requirement plan MUST define a global item and byte budget for the union of unique selected snapshot items. Each requirement MUST also define explicit coverage mode, minimum coverage (`min_items`), and at least one finite per-requirement bound across `max_items` or `max_bytes`. `max_items`, when present, MUST be at least `min_items`.

Byte cost MUST be computed from canonical UTF-8 JSON bytes of the candidate's canonical semantic representation. `minimum` coverage stops at sufficient eligible material, `all_eligible` requires every eligible non-conflicting semantic key, and `semantic_keys` requires every declared key to be selected or legally disposed. Selection order and tie-breaking MUST be deterministic. A reused item counts once against the global budget. Required material MUST never be silently truncated. Per-requirement or global budget exhaustion follows the affected requirement's missing-data policy in canonical priority order.

### INV-CTX-027: Compiled-context digest is acyclic

`CompiledTaskContext` MUST NOT contain its own digest in any field that participates in its canonical digest.

`ContextProvenance` MUST NOT contain `context_digest`.

The context digest is computed from the finished canonical context and then carried externally as `RuntimeBundle.digests()["context"]` and `ExecutionPacket.compiled_task_context_digest`.

### INV-CTX-028: Irrelevant snapshot input does not change semantic identity

Whole input-snapshot digests MUST NOT be embedded in `CompiledTaskContext` if doing so would cause unselected irrelevant input to alter compiled semantic identity.

Context provenance MUST identify the material discovery items that affected routing/materiality and the detailed selected source items, with their immutable coordinates/digests, plus task-scope, discovery, requirement-plan, kernel, and compiler semantic identities required to reproduce the compiled context. Compiler semantic identity MUST be explicit and installed-artifact safe; canonical output MUST NOT depend on ambient Git state, checkout paths, branch names, or repository availability.

An irrelevant snapshot addition MUST NOT change `CompiledTaskContext.sha256()` or bundle semantic digest.

### INV-CTX-029: Compiled context participates in runtime semantic identity

The deterministic context digest MUST participate in the runtime bundle semantic digest. Material compiled-context change MUST change runtime semantic identity even when task text is unchanged.

### INV-CTX-030: ExecutionPacket carries compiled cognitive context

The canonical execution packet MUST contain a canonical lossless representation of `CompiledTaskContext` plus its externally computed digest.

Adapters MUST NOT rebuild, weaken, or reinterpret task context independently.

### INV-CTX-031: Adapter projections preserve compiled-context identity

All adapters are renderers, not sources of semantic law. They MUST preserve required obligations, unresolved unknowns, applicable law, authority limits, capability gaps, context provenance, and compiled-context digest.

### INV-CTX-032: Deterministic compilation

For identical normalized task input, verified pack sources, governed snapshot content, selected kernel inputs, governing rules, and explicit compiler semantic identity, compilation MUST produce byte-identical canonical `CompiledTaskContext` and semantic digests regardless of input list ordering or process identity. Compiler semantic identity MUST use installed-artifact-safe fields such as package version plus a deliberate compiler semantics version. Ambient Git HEAD, branch, checkout path, current time, process ID, hostname, or repository availability MUST NOT participate in canonical semantics.

### INV-CTX-033: The semantic compiler forbids external acquisition and side effects

Semantic compiler modules MUST NOT perform repository mutation, shell execution, network I/O, database writes, telemetry export, provider execution, or context-source acquisition.

Manifest-bound local pack reads required to compile deterministic semantics are permitted. External hosts provide governed snapshots.

### INV-CTX-034: No observability ownership

Observability is not a primary or secondary semantic concern of this repository.

The repository MUST NOT own or introduce trace/span lifecycle, observability event models, telemetry exporters/consumers, metrics pipelines, sampling policy, logging backends, observability identity generation, failure-classification telemetry vocabularies, OpenTelemetry integration, or `l9-observability-core` integration.

An outer execution host MAY observe Cog. Cog returns compiler artifacts, digests, provenance, validation semantics, and compiler receipts only.

### INV-CTX-035: No world-state or memory-store ownership

The repository MUST NOT become the canonical world-state database, semantic memory store, Git topology ledger, authority registry, or organization dependency database.

It compiles task-scoped views supplied through governed typed boundaries.

### INV-CTX-036: No provider-specific semantic fork

Provider or tool adapters MUST NOT create a second interpretation of task scope, context, law, authority, obligations, or validation requirements.

Provider capability acceptance MAY determine executable versus governed handoff, but it operates on the same canonical packet.

### INV-CTX-037: Fail closed on semantic incompleteness

Compilation MUST fail closed, preserve an explicit governed unknown, or produce a legitimate governed block when required context, kernel, authority, capability, revision, or validation path cannot be resolved according to its declared policy.

The compiler MUST NOT manufacture confidence from absence.

### INV-CTX-038: Museum artifacts never regain live authority

Static examples, golden fixtures, generated contracts, archived packs, or compatibility files MUST NOT become fresh-mission semantic authority because they exist.

Compatibility surfaces delegate to the live compiler or remain inert.

### INV-CTX-039: Context liveness is mechanically validated

Compile-time liveness MUST preserve every existing live check and add semantic context checks for requirement disposition, provenance, relevance binding, selected-kernel identity, context-digest preservation, unknown conservation, and packet preservation.

Repository architecture drift checks such as forbidden imports/modules MAY be implemented as static tests rather than executed on every compile.

### INV-CTX-040: Backward compatibility cannot preserve architectural defects

Current CLI, MCP, HTTP, and Python-call behavior SHOULD remain compatible where that does not violate these invariants.

Existing callers that provide no `ContextSnapshot` MUST continue compiling through an empty governed snapshot unless the task explicitly requires external governed facts. Compatibility MUST NOT promote raw caller hints into authority.

### INV-CTX-041: New functionality maps to the primary concern

Every new module, dependency, model, service, or integration MUST be reviewable against INV-CTX-001.

If its primary purpose is not task-scoped cognitive compilation, it MUST be rejected, moved behind a host/source boundary, or placed in the repository that owns that concern.

### INV-CTX-042: Validation claims preserve baseline truth

A context-native change MUST distinguish pre-existing upstream failures from regressions introduced by the context work.

A pre-existing mandatory failure MUST NOT be relabeled as context success, and final PR/release readiness MUST remain blocked until all mandatory checks for the final state pass or the upstream failure is separately resolved by authorized work.

## 3. Canonical CompiledTaskContext shape

The semantic minimum is:

```yaml
compiled_task_context:
  task_scope: {}
  relevant_entities: []
  repository_state: []
  architecture_constraints: []
  applicable_law: []
  prior_decisions: []
  dependency_context: []
  evidence_refs: []
  memory_context: []
  selected_kernels: []
  capabilities:
    required: []
    available: []
    unavailable: []
    unknown: []
  authority:
    required: []
    granted: []
    limits: []
    unknown: []
    effective_order: []
    effective_order_source: compiler_default_or_governed_context
  unresolved_unknowns: []
  provenance:
    task_scope_digest: null
    discovery_digest: null
    context_requirements_digest: null
    discovery_item_digests: {}
    selected_item_digests: {}
    kernel_digests: {}
    compiler_identity:
      package_version: null
      semantics_version: null
```

`context_digest` is deliberately absent from provenance. It is computed from this completed artifact and carried outside it. `compiler_identity` is semantic and explicit; ambient version-control state is not.

## 4. Source domains and conflict discipline

Do not flatten all context into one precedence list.

- Repository-state claims resolve against repository-state authorities.
- Governing-law claims resolve through law/authority precedence.
- Prior decisions resolve through decision status and supersession.
- Dependency claims resolve against dependency/source authority.
- Evidence supports claims but is not itself a universal override layer.
- Memory and caller hints are always non-authoritative relative to governed facts.

Conflict resolution occurs only for the same semantic key and follows the exact algorithm in the implementation specification.

## 5. Explicit non-goals

Outside semantic ownership:

- executing compiled tasks;
- scheduling agents;
- persistent semantic memory;
- canonical world-state persistence;
- telemetry or observability pipelines;
- trace/span identity;
- transport routing and Gate ownership;
- repository mutation engines;
- CI orchestration;
- provider/model selection;
- general-purpose web or repository crawling.

Cog MAY compile requirements for these capabilities and consume verified facts about them. It MUST NOT absorb their implementation ownership.

## 6. Definition of DONE

Context-native compilation is DONE only when a compile mechanically explains:

- exact task scope;
- relevant entities/repository facts and their immutable coordinates;
- applicable architecture constraints and why they apply;
- applicable law and authority order source;
- active versus superseded decisions;
- material dependencies;
- evidence supporting governed claims;
- useful but non-authoritative memory;
- exact kernel bindings used downstream;
- required versus available capabilities;
- required versus granted authority and limits;
- material unresolved unknowns and their missing policies;
- provenance for every material selected item;
- deterministic reasons unrelated context was excluded.

The context digest MUST participate in bundle semantic identity and the execution packet. Existing PR #39 compiler-spine, obligation-conservation, liveness, adapter, museum-artifact, and deployment-closure guarantees MUST remain intact.
