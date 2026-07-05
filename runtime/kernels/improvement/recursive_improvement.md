---
kernel_id: recursive_improvement.v1
canonical_name: Recursive Improvement Kernel
category: improvement
status: ACTIVE
supersedes:
  - "10X Kernels/Recursive Improvement (L9).md"
source_role: "Improvement loop retained, narrowed, and gated."
---

# Recursive Improvement Kernel

## Purpose
Run bounded improvement passes that preserve strengths, fix blockers first, remove entropy, and converge when another pass adds no material value.

## Load When
- A blueprint, pack, contract, kernel, or workflow needs hardening after alignment and gap/stub validation.

## Improvement Loop
1. Preserve: identify what is already working and must not be damaged.
2. Fix blockers: address gaps that prevent execution, validation, or safe use.
3. Harden: improve specificity, contracts, authority order, and failure handling.
4. Deduplicate: collapse overlapping instructions into one governing rule.
5. Validate: map each improvement to evidence or an explicit Unknown.
6. Converge: stop when changes become cosmetic or lower leverage.

## Output Contract
- `preserved_strengths`
- `blockers_fixed`
- `dedupe_decisions`
- `hardening_changes`
- `validation_evidence`
- `remaining_unknowns`
- `convergence_status`

## Hard Bans
- Do not expand scope unless it removes a blocker or compounds reuse.
- Do not weaken constraints for convenience.
- Do not optimize wording while leaving structural defects intact.
