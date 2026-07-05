#!/usr/bin/env python3
from __future__ import annotations

from _common import STATUS_FAIL, STATUS_PASS, base_parser, emit, load_yaml, rel, resolve_root

EXPECTED_COUNTS = {
    "constitutional_law": 5,
    "task_execution": 5,
    "architecture_decision": 3,
    "improvement": 4,
    "terminal_execution": 1,
}


def main() -> int:
    parser = base_parser("Validate kernel role map directories and expected role cardinality.")
    args = parser.parse_args()
    root = resolve_root(__file__, args.root)
    role_map_path = root / "runtime/kernel_pipeline/KERNEL_ROLE_MAP.yaml"
    findings: list[str] = []

    if not role_map_path.exists():
        findings.append("Missing runtime/kernel_pipeline/KERNEL_ROLE_MAP.yaml")
        return emit({"validator": "validate_kernel_roles", "status": STATUS_FAIL, "findings": findings}, args.json)

    role_map = load_yaml(role_map_path).get("role_map", {})
    missing_roles = [role for role in EXPECTED_COUNTS if role not in role_map]
    if missing_roles:
        findings.append(f"Missing role_map entries: {missing_roles}")

    for role, expected_count in EXPECTED_COUNTS.items():
        entry = role_map.get(role, {})
        directory = entry.get("directory")
        if not directory:
            findings.append(f"Role {role} has no directory.")
            continue
        dir_path = root / directory
        if not dir_path.exists():
            findings.append(f"Role {role} directory missing: {directory}")
            continue
        files = sorted([p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in {".yaml", ".yml", ".md"}])
        if len(files) != expected_count:
            findings.append(f"Role {role} expected {expected_count} kernel files, found {len(files)} in {directory}")

    terminal_dir = root / "runtime/kernels/terminal"
    terminals = list(terminal_dir.glob("*")) if terminal_dir.exists() else []
    terminal_contracts = [p for p in terminals if p.is_file() and p.name == "flawless_victory.contract.yaml"]
    if len(terminal_contracts) != 1:
        findings.append("Exactly one terminal flawless_victory.contract.yaml is required.")

    status = STATUS_PASS if not findings else STATUS_FAIL
    if not findings:
        findings.append("Kernel role directories and cardinalities match the clean pack contract.")
    return emit({"validator": "validate_kernel_roles", "status": status, "findings": findings, "role_map_path": rel(role_map_path, root)}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
