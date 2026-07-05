---
kernel_id: recursive_alignment.v1
canonical_name: Recursive Alignment Kernel
category: improvement
status: ACTIVE
supersedes:
  - "10X Kernels/Recursive Alignment.md"
source_role: "Alignment pass only; deduped from broader 10X workflow."
---

# Recursive Alignment Kernel

## Purpose
Keep work aligned to the active objective, source intent, architecture boundaries, and authority order before improvement or execution begins.

## Load When
- A pack, blueprint, contract, or repo workflow is being cleaned, consolidated, or migrated.
- There is risk of prompt drift, scope creep, profile/kernel confusion, or authority conflict.

## Operating Rules
1. Restate the active objective in one sentence.
2. Identify source-of-truth artifacts and authority order.
3. Separate confirmed facts, inferences, and Unknowns.
4. Detect drift against the active architecture.
5. Produce only alignment decisions that change downstream execution.

## Output Contract
- `alignment_status`: aligned | partial | blocked
- `source_intent`: preserved | at_risk | unknown
- `active_scope`
- `out_of_scope`
- `boundary_decisions`
- `unknowns`
- `next_phase_allowed`: true | false

## Hard Bans
- Do not create new workstreams during alignment.
- Do not invent missing source files or decisions.
- Do not proceed to improvement if the objective or authority order is unresolved.
