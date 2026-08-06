# Schema ↔ Model Compatibility Findings (L9CR-MCP-002)

## Schema-model mapping

| Schema / artifact | Model | Notes |
|---|---|---|
| `contracts/intent_contract.schema.json` | `IntentContract` | Required fields mirrored; optional `source_context`, `unknowns` |
| `contracts/execution_contract.schema.json` | `ExecutionContract` | `contract_type` const enforced |
| `contracts/validation_contract.schema.json` | `ValidationContract` | `allowed_statuses` enum mirrored as `ValidationStatus` |
| `contracts/handoff_contract.schema.json` | `HandoffContract` | Required fields mirrored |
| `contracts/adapter_render.schema.json` | `AdapterRender` | Adapter enum mirrored as `AdapterName` |
| `runtime/execution_graph/graph.schema.json` | `ExecutionGraph` (+ node/edge) | Edge `from`/`to` mapped via aliases |

## Unresolved / intentional discrepancies

1. **Fail-closed extras:** JSON Schemas for Intent and Execution Graph set `additionalProperties: true`. Models use `extra="forbid"` so unknown fields are rejected (`UnknownFieldError`). This is intentional per contract acceptance (“invalid and unknown data rejected”).
2. **HANDOFF `unknowns: null`:** Repo YAML historically emits a null. Schema requires an array. Model coerces `null` → `[]` and documents the compatibility shim; schema change is out of scope.
3. **No schema edits:** Schema files were not modified (out of scope). Compatibility is handled in models/tests only.

## Canonical fixture

- `tests/fixtures/models/intent_canonical.json`
- `tests/fixtures/models/intent_digest.txt`
