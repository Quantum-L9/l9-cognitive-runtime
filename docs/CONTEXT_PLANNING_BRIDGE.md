# Context Planning Bridge

## Purpose

`l9-cognitive-runtime` owns **cognitive demand**, not context acquisition.

The bridge exposes the demand Cog already derives internally so an outer host can
retrieve only the governed facts the task actually needs. It is intentionally
producer-neutral. This repository does not import Topology, Graphiti, Ops, GitHub,
or any authority registry.

```text
PLAN
CompileRequest + minimal governed discovery snapshot
        -> ContextPlan

FULFILL (outside this repository)
ContextPlan
        -> authoritative context sources
        -> ContextSnapshot

COMPILE
CompileRequest + ContextSnapshot + expected_context_plan_id
        -> recompute ContextPlan
        -> require identity match
        -> CompiledTaskContext
        -> obligations / execution / validation / handoff / graph
        -> ExecutionPacket
```

## ContextPlan authority

`ContextPlan` is `l9.context-plan/v1`. Its identity binds:

- canonical task scope;
- bounded discovery projection;
- exact typed `ContextRequirementPlan`;
- active kernel source digests;
- verified runtime-pack manifest digest;
- routing-rules digest;
- pipeline digest;
- installed compiler semantics identity.

The plan contains no acquired facts. It tells an outer host **what Cog requires**,
not where or how the host must retrieve it.

## Fulfillment ownership

A future outer context control plane may project authoritative sources into the
existing `ContextSnapshot` buckets:

| Snapshot kind | Expected authority class |
|---|---|
| repository state / relevant entities / dependencies | observed architecture or repository evidence |
| architecture constraints / applicable law / prior decisions | governed policy and decision sources |
| evidence refs | originating evidence owner |
| memory context | non-authoritative memory |
| capability facts | capability authority |
| authority facts | explicit authority source |

Those mappings are intentionally not implemented here. `L9-Ops-MCP` integration is
deferred; no placeholder client or adapter is added to Cog.

## Replan law

Final compilation accepts an optional `expected_context_plan_id`. When supplied,
Cog recomputes the plan from the final snapshot before deriving execution semantics.
A changed discovery signal, route, kernel digest, requirement, or governing compiler
input changes the ID and compilation fails with `replan required`.

Fulfillment that adds facts which do not alter discovery or cognitive demand does not
invalidate the plan. This is deliberate: plan identity binds semantic demand, not a
hash of irrelevant raw context.

## Kernel-declared needs

Kernel selection can change demand. Canonical YAML kernels may declare typed
`context_needs`; the existing `KernelResolver` digests and validates those needs and
the `ContextRequirementPlanner` turns them into requirements with `kernel_need_refs`.

The Global Architect kernel now dogfoods this seam for architecture constraints,
dependency context, and prior architecture decisions. These declarations are
optional so legacy empty-context compilation remains valid while the outer context
control plane is still deferred.

## Public surfaces

- Python: `CognitiveRuntimeService.plan_context(...)`
- CLI: `--plan-context`
- MCP: `plan_context_requirements`
- final compile binding: `expected_context_plan_id`

HTTP remains only a transport for MCP and adds no second interpretation.

## Non-goals

This bridge does not:

- acquire context;
- call Topology or Graphiti;
- select providers;
- execute tasks;
- schedule work;
- widen authority;
- turn memory into governed truth;
- create a second kernel registry;
- create a second semantic compiler.
