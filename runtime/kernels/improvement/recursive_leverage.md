---
kernel_id: recursive_leverage.v1
canonical_name: Recursive Leverage Kernel
category: improvement
status: ACTIVE
supersedes:
  - "10X Kernels/Recursive Leverage.md"
source_role: "Final compression pass before terminal execution."
---

# Recursive Leverage Kernel

## Purpose
Compress improved artifacts into the fewest reusable primitives, phase gates, and output contracts that create compounding future value.

## Load When
- After recursive improvement and before Flawless Victory.
- When deciding whether to keep, merge, demote, or delete overlapping kernels.

## Leverage Test
A change is high leverage only if it improves one or more:
- future action speed
- repeatability
- validation strength
- drift resistance
- reuse across repos or agents
- decision quality

## Output Contract
- `keep`
- `merge`
- `remove`
- `promote_to_runtime_primitive`
- `defer`
- `highest_leverage_next_action`

## Hard Bans
- Do not confuse complexity with leverage.
- Do not keep duplicate active kernels because they sound useful.
- Do not add another kernel when a routing rule or phase gate solves the problem.
