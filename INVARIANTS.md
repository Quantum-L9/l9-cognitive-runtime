# L9 Cognitive Runtime Invariants

- Status: CANONICAL ARCHITECTURE LAW
- Scope: `Quantum-L9/l9-cognitive-runtime`
- Primary concern: deterministic task-scoped cognitive compilation

## 1. Repository identity

The L9 Cognitive Runtime is the deterministic task-to-cognitive-execution compiler. It converts a task plus governed source context into the minimum sufficient, provenance-backed cognitive context and execution packet required to perform that task correctly.

The repository does not own task execution, persistent world state, semantic memory storage, observability infrastructure, transport routing, provider infrastructure, or agent-host lifecycle management.

## 2. Primary invariants

### INV-CTX-001: Task-scoped compilation is the primary concern

Every live feature MUST materially strengthen task interpretation, task scope derivation, context requirement derivation, governed context selection and reduction, kernel/cognitive-capability selection, obligation derivation, execution/validation/handoff compilation, execution-packet compilation, or deterministic adapter projection.

A feature whose primary purpose does not strengthen that chain belongs outside this repository unless it is strictly necessary to expose, package, or validate the compiler.

### INV-CTX-002: One live compilation spine

There MUST be exactly one authoritative fresh-mission semantic spine, and it MUST be `CompilePipeline`.

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
  -> semantic digest
  -> ExecutionPacket
  -> validate_packet
  -> BundleSemanticValidator
  -> RuntimeBundle
  -> AdapterRenderer
```

Compatibility wrappers — the `runtime/` CLIs and `compiler/context.py` — MAY expose narrower entry shapes, but they MUST delegate to a `CompilePipeline`-owned entry method that joins this same internal path. They MUST NOT sequence semantic stages themselves.

Concretely: no module other than `compiler/pipeline.py` may instantiate more than one of the semantic stage owners (`ObjectiveDeriver`, `TaskScopeCompiler`, `ContextDiscoveryCompiler`, `ActivationPlanner`, `KernelResolver`, `ContextRequirementPlanner`, `ContextCompiler`, `ContextClosureValidator`, `ObligationDeriver`, `ExecutionContractCompiler`, `ValidationContractCompiler`, `HandoffContractCompiler`). A compatibility entry MUST NOT be able to bypass context closure, packet validation, or runtime semantic liveness. Adding a second orchestration module to replace one that was removed is the same defect under a new name.

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

Only the declared scope-hint keys (`target_refs`, `in_scope_refs`, `excluded_refs`) may reach compiled semantics, and only by **narrowing** task scope. Every other key — `context_signals` explicitly included — is inert. A caller hint that would affect execution semantics MUST first be supplied as a typed, provenance-backed governed context item.

Mission text remains a legitimate candidate signal of the caller's own intent; it asserts nothing about the world outside the request.

Scope exclusion is real, not decorative. An `excluded_refs` entry MUST be removed from the eligible scope reference set, so no excluded reference can select scoped context. An exact reference that appears in both the included set (`target_refs` or `in_scope_refs`) and `excluded_refs` is a scope conflict: it MUST surface as a stable blocking `AMBIGUOUS_SCOPE` `ContextUnknown` or fail closed, and MUST NOT silently resolve to include. Reference matching is exact: path-prefix, glob, ancestry, and repository-hierarchy semantics MUST NOT be invented from plain strings.

### INV-CTX-007: Governed context is a separate, bounded compiler input

Authoritative or evidence-bearing context MUST enter compilation as a typed `ContextSnapshot` or equivalent governed input separate from `CompileRequest.source_context`.

The service and compiler MAY accept `context_snapshot=None` for backward compatibility, which is equivalent to an empty governed snapshot. They MUST NOT silently promote caller hints into the governed snapshot.

The snapshot is a bounded input, not merely a bounded output. Finite input ceilings (`SNAPSHOT_MAX_ITEMS`, `SNAPSHOT_MAX_BYTES`) MUST be enforced in a preflight that runs **before** snapshot normalization or resolution. Item-count rejection MUST precede per-item resolution or hashing. Byte measurement MUST be deterministic and canonical. Exceeding either ceiling MUST fail closed; silent truncation of input is forbidden.

### INV-CTX-008: Context requirements precede detailed selection

Detailed context selection MUST be driven by an explicit typed `ContextRequirementPlan`.

Each requirement MUST define stable identity, context kind, reason, required/optional status, explicit scope mode and selectors, freshness requirement plus exact coordinate constraint when applicable, minimum authority level, deterministic priority, coverage mode, minimum coverage (`min_items`), required semantic keys when applicable, item budget, byte budget, and missing-data policy. Coverage mode MUST distinguish at least `minimum`, `all_eligible`, and `semantic_keys`. Requirement satisfaction MUST be mechanically decidable from those fields and any kind-specific rule.

Requirements derive from task scope, the bounded discovery projection, the matched route, **and the resolved kernel bindings**. A selected kernel that cannot demand context is a kernel whose selection carries no meaning (INV-CTX-020); the planner MUST consume kernel-declared context needs rather than accepting the bindings and ignoring them.

Only the bounded discovery projection is exempt from requiring the final requirement plan.

### INV-CTX-009: Context-source infrastructure stays outside the compiler

The compiler MAY define source contracts and consume immutable snapshots. It MUST NOT own GitHub crawling, Graphiti persistence, vector/database clients, network discovery, transport routing, or organization-wide state services.

This prohibition does NOT forbid immutable reads of the verified runtime pack already required by the live compiler, including routing rules, pipeline definitions, kernels, schemas, and other manifest-bound semantic sources.

### INV-CTX-010: Repository state is revision-bound

Repository facts that affect compilation MUST identify repository identity plus an exact commit, tree, content digest, or equivalent immutable coordinate.

Unbound branch names, ambient working-directory observations, or unversioned prose MUST NOT become canonical repository truth.

### INV-CTX-011: Every material context item has compiler-owned identity and provenance

Every material context item MUST have:

- stable item identity;
- context kind;
- a deterministic semantic key derived or validated from that kind's canonical recipe;
- source reference;
- explicit `scoped` or `global` scope mode;
- immutable source coordinate or content digest where the source permits it;
- authority/truth classification appropriate to its domain;
- compiler-generated relevance binding when selected.

Item identity is **compiler-owned, not caller-chosen**. `item_id` MUST be derived from — or validated against — exactly one canonical recipe binding at least the context kind, the semantic key, the canonical claim content, the stable source identity, and the immutable source coordinate or content digest when present. A supplied `item_id` that disagrees with the recipe MUST fail closed. Random UUIDs, timestamps, branch names, working directories, process identity, and caller-arbitrary identifiers MUST NOT determine identity, and MUST NOT participate in canonical semantic output.

Snapshot candidates MUST enter with empty selection bindings. The compiler MUST populate `selected_because` only after selection. Repository-state items MUST represent one semantic claim each rather than an opaque multi-fact map.

### INV-CTX-012: Ordering and deduplication are deterministic

Input list order MUST NOT change compiled semantic output.

Candidates MUST be canonically normalized and sorted before selection. Semantically identical duplicate candidates MUST collapse deterministically. Authority rank, immutable coordinate, content digest, stable semantic key, and stable item ID MUST provide explicit canonical tie-breaking. Enum declaration order and input list position MUST NOT provide hidden precedence.

### INV-CTX-013: Supersession resolves kind-wide, before same-key conflict resolution

Conflicts exist only between claims of the same context kind that address the same deterministic semantic key. Every context kind MUST define its semantic-key recipe and domain precedence rule.

Explicit supersession, however, is **not** confined to one semantic key. A law that supersedes a differently-identified law, and a decision that supersedes a differently-identified decision, are the ordinary cases. Explicit supersession relationships MUST therefore be resolved **kind-wide, across semantic keys, before** same-key conflict resolution runs. Grouping claims by their own identifier first — so that only claims sharing an identifier can ever interact — makes cross-identifier supersession structurally unreachable and is forbidden.

The supersession pass MUST:

- support `supersedes_refs` naming either an item identity or a domain identifier;
- support `PriorDecision.superseded_by_refs` in the inverse direction;
- never let an explicit `SUPERSEDED` status remain active;
- ignore self-reference: only a claim with a different domain identifier may supersede another;
- be order-independent, so inverse input order yields the same surviving set;
- fail closed on a supersession cycle, or record an explicit `UNKNOWN_SUPERSESSION` for its members, and never arbitrarily select a winner from a cycle;
- keep dangling supersession references visible rather than silently accepting them.

Only surviving claims enter precedence and authority resolution. When two surviving same-key claims differ:

- a stronger governed authority MAY supersede a weaker claim only when that context kind's domain rule permits it;
- applicable law resolves declared law precedence before generic authority rank;
- prior decisions resolve status before generic authority rank;
- memory and caller hints MUST never override governed authoritative facts;
- equal-authority contradictory governed claims MUST NOT be arbitrarily chosen and MUST become an explicit `ContextUnknown` or governed block according to the requirement's missing/conflict policy.

Evidence supports claims; evidence itself is not a generic truth-precedence layer.

### INV-CTX-014: Architecture constraints require evidence

Architecture materiality MAY consume mission text as a candidate signal, but external architecture facts MUST be established by typed discovery facts with provenance.

Kernel file presence and raw `source_context.context_signals` MUST NOT directly prove architecture materiality. A host proves an architecture signal by supplying a provenance-backed governed constraint whose identifier is the signal name; the bounded discovery projection is the only legal path from governed context to materiality.

### INV-CTX-015: Applicable law is selected, not dumped — and scoped law survives selection

The compiler MUST include only law, policy, contracts, and governance rules applicable to the compiled task scope.

Each law item MUST preserve identity, applicability reason, source provenance, and authority/precedence relationship when known.

Governing context that is *task-scoped* MUST remain eligible for detailed selection. When the task names scope references, governing requirements — architecture constraints, applicable law, prior decisions, and authority facts where scope is material — MUST be planned as task-scoped rather than global. A globally applicable governed item MAY satisfy a scoped governing requirement; a scoped item MUST NOT satisfy an unrelated scope. In particular, the governed constraint that legally fired architecture materiality MUST be eligible for the compiled context: proving materiality from an item and then discarding it is a contradiction the closure validator cannot repair.

### INV-CTX-016: Prior decisions preserve status and supersession

A prior decision MUST distinguish at least `active`, `superseded`, and `unknown` status.

Superseded decisions MUST NOT silently remain active, including when the superseding decision carries a different `decision_id` (INV-CTX-013). Material unknown supersession MUST remain visible.

### INV-CTX-017: Dependency context is task-relevant

Dependency context MUST include only upstream, downstream, package, repository, API, schema, or runtime seams materially relevant to task scope or selected kernels.

Dependency facts require source provenance. Textual proximity is not dependency authority.

### INV-CTX-018: Evidence is addressable and non-fabricated

Evidence references MUST have stable identity and an addressable locator. They SHOULD carry a digest or immutable coordinate when the source permits it.

Successful parsing, successful retrieval, or file existence MUST NOT be transformed into proof of correctness.

### INV-CTX-019: Memory is enrichment, never operational truth

`memory_context` MAY provide associative recall, historical context, experience, and semantic relationships.

Memory MUST NOT redefine current repository state, governing law, authority, exact dependencies, or validated evidence, and MUST NOT route. Material conflicts preserve governed truth and record the conflict when useful.

### INV-CTX-020: Kernel selection is part of compiled context, and kernels may demand context

Every selected kernel MUST use the existing fail-closed `KernelBinding` identity, source reference, digest, and typed output model.

`CompiledTaskContext.selected_kernels` MUST exactly equal the bindings consumed by downstream obligation and execution compilation.

A kernel MAY declare typed **context needs** in its own semantic source, so that selecting the kernel actually changes what context the compile requires. Each need MUST carry a stable need identifier, context kind, required flag, reason, coverage semantics, minimum authority, and optionally required semantic keys. Needs are declarative and non-agentic: a kernel declares *what type* of context it needs; the requirement planner binds that need to the current task scope and produces canonical `ContextRequirement`s. A kernel MUST NOT declare task-specific scope references, runtime source results, or availability claims — those are not the kernel's to know. Needs are digest-bound through the kernel source and are consumed strictly upstream of obligation derivation.

### INV-CTX-021: Capability requirement and availability are distinct

The compiler MUST separately represent capabilities that are required, proven available, proven unavailable, and unknown. Required capability is compiler-derived from task/objective/route/kernel semantics; source snapshots MAY prove availability or unavailability but MUST NOT declare the task's required capabilities.

Required MUST NOT imply available, and unavailable MUST NOT collapse into unknown. Absence of proof is an explicit state, never an implied grant:

- a required capability proven **unavailable** MUST produce a blocking `ContextUnknown`;
- a required capability with **no** governing fact MUST produce an explicit non-blocking `ContextUnknown` and MUST NOT appear as available.

### INV-CTX-022: Authority requirement, grant, limit, and effective order are distinct

The compiler MUST separately represent required authority, proven grants, explicit limits, and unknown authority. Required authority is compiler-derived from task/objective/route/kernel semantics; source snapshots MAY prove grants, limits, or unknown state but MUST NOT declare what authority the task requires.

Required MUST NOT imply granted. Absence of a grant is an explicit state:

- a required authority proven **limited** MUST produce a blocking `ContextUnknown`;
- a required authority with **no** proven grant MUST produce an explicit non-blocking `ContextUnknown`, whether or not any authority fact was supplied at all. Reasoning about a gap only when some authority plane happens to exist makes the empty case silently permissive.

Context-specific governing authority order MUST take precedence when proven. For backward compatibility, the current compiler authority order MAY remain as an explicit `compiler_default` only when no more specific governed order is available. The output MUST identify whether its effective order came from governed context or the compiler default. The compiler default is a **precedence fallback and never a grant**: it MUST NOT satisfy a required authority.

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

### INV-CTX-025: Context closure precedes execution semantics, and every check proves its name

A context-closure validator MUST run before downstream execution semantics are considered valid.

It MUST verify required requirement disposition, provenance, semantic-key recipes, relevance bindings, exact kernel equality, same-key conflict disposition, memory non-authority, capability/authority gaps, budget compliance, and unknown conservation.

A named check MUST prove the property it names. Specifically:

- **conflict disposition** MUST hold over every *eligible* conflicting governed semantic key a requirement would have matched, not merely over keys that also happen to appear in the selected set. A conflict that disappears entirely is the case the check exists to catch;
- **budget compliance** MUST recompute each requirement's own selected item count and canonical byte cost from the finished context and verify that requirement's `max_items`, `max_bytes`, `min_items`, and coverage mode, **and independently** verify the global unique-item budget. A per-requirement breach that fits inside the global budget MUST be detected;
- **capability and authority gaps** MUST prove that every compiler-derived required capability and required authority has exactly one explicit disposition — available/granted, unavailable/limited, or explicit unknown.

Closure MUST enforce exact executed-check coverage the same way runtime liveness does: a declared check that does not execute is a failure, not a quietly shorter report.

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

### INV-CTX-030: ExecutionPacket carries compiled cognitive context, verifiably

The canonical execution packet MUST contain a canonical lossless representation of `CompiledTaskContext` plus its externally computed digest.

Packet validation MUST **recompute** the canonical digest of the carried context body and require it to equal the declared `compiled_task_context_digest`, and require the packet provenance to carry the same digest. Carrying a digest that nothing checks against the body is metadata, not integrity: a mutated context body with an unchanged declared digest MUST fail packet validation.

Adapters MUST NOT rebuild, weaken, or reinterpret task context independently.

### INV-CTX-031: Adapter projections preserve the compiled-context body and identity

All adapters are renderers, not sources of semantic law. An adapter packet MUST carry the compiled task context **losslessly** — the body, not only the digest — and MUST carry the digest through unchanged rather than recomputing it.

Adapters MUST preserve required obligations, unresolved unknowns, applicable law, authority limits, capability gaps, and context provenance. A textual adapter projection MUST include or reference the canonical context rather than re-deriving it. An adapter MUST NOT reselect context, summarize away blocking context, or recompute governance or authority.

### INV-CTX-032: Deterministic compilation

For identical normalized task input, verified pack sources, governed snapshot content, selected kernel inputs, governing rules, and explicit compiler semantic identity, compilation MUST produce byte-identical canonical `CompiledTaskContext` and semantic digests regardless of input list ordering or process identity. Compiler semantic identity MUST use installed-artifact-safe fields such as package version plus a deliberate compiler semantics version. Ambient Git HEAD, branch, checkout path, current time, process ID, hostname, or repository availability MUST NOT participate in canonical semantics.

### INV-CTX-033: The semantic compiler forbids external acquisition and side effects

Semantic compiler modules MUST NOT perform repository mutation, shell execution, network I/O, database writes, telemetry export, provider execution, or context-source acquisition.

Manifest-bound local pack reads required to compile deterministic semantics are permitted. External hosts provide governed snapshots.

### INV-CTX-034: No observability ownership

Observability is not a primary or secondary semantic concern of this repository.

The repository MUST NOT own or introduce trace/span lifecycle, observability event models, telemetry exporters/consumers, metrics pipelines, sampling policy, logging backends, observability identity generation, failure-classification telemetry vocabularies, OpenTelemetry integration, or `l9-observability-core` integration.

An outer execution host MAY observe the runtime. The runtime returns compiler artifacts, digests, provenance, validation semantics, and compiler receipts only.

### INV-CTX-035: No world-state or memory-store ownership

The repository MUST NOT become the canonical world-state database, semantic memory store, Git topology ledger, authority registry, or organization dependency database.

It compiles task-scoped views supplied through governed typed boundaries.

### INV-CTX-036: No provider-specific semantic fork

Provider or tool adapters MUST NOT create a second interpretation of task scope, context, law, authority, obligations, or validation requirements.

Provider capability acceptance MAY determine executable versus governed handoff, but it operates on the same canonical packet.

### INV-CTX-037: Fail closed on semantic incompleteness

Compilation MUST fail closed, preserve an explicit governed unknown, or produce a legitimate governed block when required context, kernel, authority, capability, revision, or validation path cannot be resolved according to its declared policy.

The compiler MUST NOT manufacture confidence from absence. A successful compile MUST NOT imply that permission or capability exists.

### INV-CTX-038: Museum artifacts never regain live authority

Static examples, golden fixtures, generated contracts, archived packs, or compatibility files MUST NOT become fresh-mission semantic authority because they exist.

Compatibility surfaces delegate to the live compiler or remain inert.

### INV-CTX-039: Liveness is mechanically validated, and no check may pass vacuously

Compile-time liveness MUST preserve every existing live check and add semantic context checks for requirement disposition, provenance, relevance binding, selected-kernel identity, context-digest preservation, unknown conservation, and packet preservation.

Every check declared in the validator's check ladder MUST actually execute and MUST evaluate a computed condition. The following are forbidden, because each reports a guarantee that was never evaluated:

- appending a check name to the executed list without computing anything;
- a condition that is a literal constant, or a tautology over the declaration the check is supposed to be verifying;
- making a required input optional so the check can be skipped when the input is absent.

`every_required_kernel_output_exists` MUST be a real semantic check: for every required `KernelOutput` of every active `KernelBinding`, the output MUST be present in `output_refs` on an `ExecutionStep` that actually invokes the declaring kernel, and — since the graph carries the same output contract — MUST be preserved into the corresponding graph node rather than assumed correct by derivation.

The execution packet is a required liveness input, not an optional one, and packet validation MUST precede final liveness success.

Repository architecture drift checks such as forbidden imports/modules MAY be implemented as static tests rather than executed on every compile.

### INV-CTX-040: Backward compatibility cannot preserve architectural defects

Current CLI, MCP, HTTP, and Python-call behavior SHOULD remain compatible where that does not violate these invariants.

Existing callers that provide no `ContextSnapshot` MUST continue compiling through an empty governed snapshot unless the task explicitly requires external governed facts. Compatibility MUST NOT promote raw caller hints into authority.

Where a legacy command's invocation shape cannot be preserved without creating a second semantic compiler, the CLI MUST be preserved as a projection over the canonical pipeline rather than the architectural defect being preserved.

### INV-CTX-041: New functionality maps to the primary concern

Every new module, dependency, model, service, or integration MUST be reviewable against INV-CTX-001.

If its primary purpose is not task-scoped cognitive compilation, it MUST be rejected, moved behind a host/source boundary, or placed in the repository that owns that concern. Runtime dependencies MUST remain `mcp`, `pydantic`, and `PyYAML` unless repository law explicitly requires otherwise.

### INV-CTX-042: Validation claims preserve baseline truth

A context-native change MUST distinguish pre-existing upstream failures from regressions introduced by the context work.

A pre-existing mandatory failure MUST NOT be relabeled as context success, and final PR/release readiness MUST remain blocked until all mandatory checks for the final state pass or the upstream failure is separately resolved by authorized work. A check that was not executed MUST be reported as not executed, never as passed.

### INV-CTX-043: Public runtime surfaces can receive governed context

Governed context is useless if only the in-process Python caller can supply it. Every public compile surface MUST be able to accept a typed `ContextSnapshot`:

- the Python service accepts it as a keyword-only argument, separate from `CompileRequest.source_context`;
- the CLI accepts an optional typed serialization (a JSON file). Reading that file is outer-host I/O performed by the CLI, never by the semantic compiler; the payload MUST validate into a `ContextSnapshot` before compilation, and an invalid payload MUST fail closed;
- the MCP surface accepts an optional typed context payload on `compile_runtime`, `plan_kernel_activation`, and `validate_runtime_bundle`. `compile_intent` need not accept it, because intent semantics do not depend on it. An invalid payload MUST fail closed;
- HTTP remains a transport for the MCP surface. A second HTTP-specific context interpreter MUST NOT be added.

Advertised runtime capabilities MUST state that governed context snapshot input is supported. The same mission plus the same snapshot MUST produce the same compiled context and semantic digests across every surface.

### INV-CTX-044: Deployment closure is proven by compiling, not by listing

The sealed deployment pack MUST contain the compiled-context schema and MUST prove that every supported route compiles from the pack itself, recording each route's compiled-context digest as closure evidence. A sealed runtime MUST compile with no repository checkout.

The container smoke MUST exercise a real MCP `initialize` **and a real `compile_runtime` call** against the deployed container. Asserting that a tool name appears in a capability listing proves the listing, not the compiler. The smoke MUST assert the call is not an error and that the result carries a semantic digest, a context digest, an execution packet containing the compiled task context, and a compiled-context digest matching the packet provenance. Replacing the real MCP smoke with a direct in-process Python call is forbidden.

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
- Governing-law claims resolve through explicit supersession, then law precedence, then authority.
- Prior decisions resolve through explicit supersession and decision status, then authority.
- Dependency claims resolve against dependency/source authority.
- Evidence supports claims but is not itself a universal override layer.
- Memory and caller hints are always non-authoritative relative to governed facts.

Explicit supersession is resolved kind-wide first (INV-CTX-013). Only then does same-semantic-key conflict resolution run, following the exact algorithm in the implementation.

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

The runtime MAY compile requirements for these capabilities and consume verified facts about them. It MUST NOT absorb their implementation ownership.

## 6. Definition of DONE

Context-native compilation is DONE only when a compile mechanically explains:

- exact task scope, including what was excluded and why;
- relevant entities/repository facts and their immutable coordinates;
- applicable architecture constraints and why they apply;
- applicable law, its supersession lineage, and authority order source;
- active versus superseded decisions;
- material dependencies;
- evidence supporting governed claims;
- useful but non-authoritative memory;
- exact kernel bindings used downstream, and the context those kernels demanded;
- required versus available capabilities, with absence explicit;
- required versus granted authority and limits, with absence explicit;
- material unresolved unknowns and their missing policies;
- provenance for every material selected item;
- deterministic reasons unrelated context was excluded.

The context digest MUST participate in bundle semantic identity and the execution packet. Existing compiler-spine, obligation-conservation, liveness, adapter, museum-artifact, and deployment-closure guarantees MUST remain intact — including the packet-gate enforcement that made `validate_packet` run on every fresh compile, made the packet a required liveness input, made `no_adapter_drops_blocking_obligation` a real computed check, and made liveness check coverage mechanically asserted.
