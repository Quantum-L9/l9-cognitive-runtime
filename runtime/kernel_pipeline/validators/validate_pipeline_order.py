#!/usr/bin/env python3
from __future__ import annotations

from _common import STATUS_FAIL, STATUS_PASS, base_parser, emit, load_yaml, rel, resolve_root

EXPECTED_PHASES = [
    "P0_UNPACK",
    "P1_CONSTITUTIONAL_PREFLIGHT",
    "P2_TASK_ROUTING",
    "P3_ARCHITECTURE_DECISION",
    "P4_ALIGNMENT_AND_STUB_GATE",
    "P5_RECURSIVE_IMPROVEMENT",
    "P6_LEVERAGE_COMPRESSION",
    "P7_FLAWLESS_VICTORY",
]

CONSTITUTIONAL_ORDER = [
    "runtime/kernels/constitutional/K01-platform-architecture-engine.yaml",
    "runtime/kernels/constitutional/K02-contracts-code-laws-enforcement.yaml",
    "runtime/kernels/constitutional/K03-constellation-transport-authority.yaml",
    "runtime/kernels/constitutional/K04-domain-spec-yaml-authoring.yaml",
    "runtime/kernels/constitutional/K05-file-ownership-placement-capability-registry.yaml",
]
TERMINAL = "runtime/kernels/terminal/flawless_victory.contract.yaml"


def main() -> int:
    parser = base_parser("Validate canonical kernel pipeline order and terminal-only Flawless Victory activation.")
    args = parser.parse_args()
    root = resolve_root(__file__, args.root)
    pipeline_path = root / "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"
    findings: list[str] = []

    if not pipeline_path.exists():
        findings.append("Missing runtime/kernel_pipeline/KERNEL_PIPELINE.yaml")
        return emit({"validator": "validate_pipeline_order", "status": STATUS_FAIL, "findings": findings}, args.json)

    pipeline = load_yaml(pipeline_path)
    phases = pipeline.get("phase_order", [])
    phase_ids = [p.get("id") for p in phases]

    if phase_ids != EXPECTED_PHASES:
        findings.append(f"Phase order mismatch: expected {EXPECTED_PHASES}, found {phase_ids}")

    for phase in phases:
        phase_id = phase.get("id", "UNKNOWN_PHASE")
        for kernel in phase.get("primary_kernels", []):
            if not (root / kernel).exists():
                findings.append(f"{phase_id} references missing kernel: {kernel}")

    p1 = next((p for p in phases if p.get("id") == "P1_CONSTITUTIONAL_PREFLIGHT"), {})
    if p1.get("primary_kernels") != CONSTITUTIONAL_ORDER:
        findings.append("P1 constitutional kernel order is not exactly K01 -> K05.")

    terminal_refs = []
    for phase in phases:
        for kernel in phase.get("primary_kernels", []):
            if kernel == TERMINAL:
                terminal_refs.append(phase.get("id"))
    if terminal_refs != ["P7_FLAWLESS_VICTORY"]:
        findings.append(f"Flawless Victory must be terminal-only in P7; found in {terminal_refs}")

    if pipeline.get("terminal_contract") != TERMINAL:
        findings.append("terminal_contract does not point to runtime/kernels/terminal/flawless_victory.contract.yaml")

    status = STATUS_PASS if not findings else STATUS_FAIL
    if not findings:
        findings.append("Pipeline order, kernel references, constitutional order, and terminal-only rule are valid.")
    return emit({"validator": "validate_pipeline_order", "status": status, "findings": findings, "root": rel(root, root.parent)}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
