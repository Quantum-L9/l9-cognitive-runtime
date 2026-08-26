# Compile observability lifecycle

`CognitiveRuntimeService.compile_runtime()` owns the producer lifecycle boundary for compile
observability. Protocol adapters do not project observations independently.

## Runtime boundary

The service accepts an optional `CompileObserver` and optional per-call
`RuntimeInvocationContext`.

```text
CompileRequest + RuntimeInvocationContext
              |
              v
CognitiveRuntimeService.compile_runtime()
              |
              +--> CompileObserver.start(...)
              |        |
              |        +--> CompileObservationSession.succeeded(bundle)
              |        `--> CompileObservationSession.failed(error)
              |
              `--> original RuntimeBundle or original compile exception
```

Observer calls are a side channel. Once a compile is invoked, observer start/terminal failures
must never replace a successful `RuntimeBundle` or the original compile exception. An optional
`ObserverErrorReporter` may receive observer failures; failure of that reporter is lower authority
and is also suppressed.

## Invocation context

`RuntimeInvocationContext` is separate from `CompileRequest` because execution lineage is not
business input. It may carry upstream trace/program/campaign/task/run/attempt/session coordinates.
Missing coordinates remain `None`.

The MCP in-memory run-store ID is a result-resource identity created after compilation. It is not
implicitly promoted into canonical execution `run_id`. A caller that owns a canonical run identity
must supply it through the invocation context.

## Protocol adapters

CLI, MCP stdio, and MCP HTTP all construct or reuse the same central service observer. They do not
call projection helpers separately. MCP/HTTP may inject a per-call invocation-context factory.

## Canonical event projection

The lifecycle seam is independent of any event package. The canonical `l9-observability-core`
adapter belongs in `l9_cognitive_runtime.observability` once an authoritative core package source
is available. That adapter must preserve these boundaries:

- identity allocation is injected; the adapter does not invent organization-wide ID law;
- timing is injected; projection helpers remain deterministic;
- failure classification is injected and sanitized;
- canonical event handoff uses an injected consumer port;
- transport, persistence, retry delivery, storage, assurance admission, World Model admission, and
  memory projection remain outside Cognitive Runtime and outside `l9-observability-core`;
- a successful compile produces a terminal completed span;
- a failed compile produces a terminal failed span and, when classification is available, a
  separately identified causal failure event.

## Activation

With no observer configured, runtime behavior is unchanged. If a deployment later declares
canonical observability required, adapter/dependency initialization must fail activation explicitly
when its required package or configured dependencies are absent. Per-operation observer failures
remain non-interfering once the business operation starts.

## Required regression proof

A release claiming runtime-live compile observability must prove all of the following against actual
entrypoints:

1. a real `RuntimeBundle` reaches the observer exactly once on success;
2. the original exception reaches the observer exactly once on failure and is re-raised unchanged;
3. observer failures cannot alter either business outcome;
4. invocation context values are preserved and absent values are not manufactured;
5. CLI, MCP stdio, and MCP HTTP converge on the central service boundary;
6. protocol wrappers do not double-observe;
7. MCP result-resource IDs are not silently treated as canonical execution IDs.
