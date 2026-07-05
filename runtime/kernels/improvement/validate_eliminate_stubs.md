---
kernel_id: validate_eliminate_stubs.v1
canonical_name: Validate & Eliminate Stubs Kernel
category: improvement
status: ACTIVE
supersedes:
  - "10X Kernels/Validate & Fill Gaps.md"
  - "10X Kernels/Validate & Eliminate Stubs.md"
source_role: "Merged gap-fill and stub-elimination into one enforcement kernel."
---

# Validate & Eliminate Stubs Kernel

## Purpose
Find real gaps, placeholders, fake completeness, thin sections, broken contracts, and pass-only validation claims. Convert them into concrete remediation or block execution.

## Load When
- Preparing a build contract.
- Auditing generated artifacts.
- Checking whether a pack is complete enough for execution.
- Preventing TODO/stub/placeholder leakage.

## Scan Targets
- TODO / FIXME / placeholder / stub / NotImplemented / TBD / coming soon.
- Empty or generic sections that claim production readiness without substance.
- Validation claims without commands, logs, outputs, reports, or blocker notes.
- Missing output contracts, acceptance criteria, authority order, stop conditions, or evidence requirements.

## Output Contract
- `gap_inventory`
- `stub_inventory`
- `fake_validation_findings`
- `remediation_actions`
- `blockers`
- `execution_allowed`: true | false

## Hard Bans
- Do not mark validation as passed without evidence.
- Do not fill gaps with generic prose.
- Do not preserve a stub because it is documented. Documented stubs are still stubs unless intentionally deferred and gated.
