---
kernel_id: "validate_eliminate_stubs.v1"
canonical_name: "Validate & Eliminate Stubs Kernel"
category: "improvement"
status: "ACTIVE"
supersedes:
  - "10X Kernels/Validate & Fill Gaps.md"
  - "10X Kernels/Validate & Eliminate Stubs.md"
source_role: "Merged gap-fill and stub-elimination into one enforcement kernel."
id: "l9-cognitive-runtime.kernel.runtime_kernels_improvement_validate_eliminate_stubs__md"
title: "validate eliminate stubs"
artifact_type: "kernel"
mcp_primitive: "tool"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "runtime/kernels/improvement/validate_eliminate_stubs.md"
content_hash: "cd1c576fcf2055cbe0359192302704b7134002c1c97221afe8a27d544303ce4b"
token_cost_estimate: 288
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "auditor"
description: "Unknown"
activation_signals: ["validate", "scan", "build", "kernel", "find", "contract"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
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
