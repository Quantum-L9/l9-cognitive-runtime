# Execution Graph

- `front_end_intake`: Phase 0 Front-End / Intent Intake -> FRONT_END_INTAKE.md
- `semantic_preflight`: Phase 1 Semantic Analysis / Constitutional Preflight -> SEMANTIC_PREFLIGHT.md
- `strategic_expansion`: Phase 2 Strategic Expansion -> STRATEGIC_EXPANSION.md
- `architecture_synthesis`: Phase 3 Architecture Synthesis -> ARCHITECTURE_SYNTHESIS.md
- `structural_validation`: Phase 4 Structural Validation -> STRUCTURAL_VALIDATION.md
- `optimization`: Phase 5 Optimization -> OPTIMIZATION.md
- `global_optimization`: Phase 6 Global Optimization -> GLOBAL_OPTIMIZATION.md
- `emission`: Phase 7 Emission -> EMISSION.md

## Edges
- `front_end_intake` -> `semantic_preflight` (phase_order)
- `semantic_preflight` -> `strategic_expansion` (phase_order)
- `strategic_expansion` -> `architecture_synthesis` (phase_order)
- `architecture_synthesis` -> `structural_validation` (phase_order)
- `structural_validation` -> `optimization` (phase_order)
- `optimization` -> `global_optimization` (phase_order)
- `global_optimization` -> `emission` (phase_order)
