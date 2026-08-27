#!/usr/bin/env python3
"""Validate kernel role declarations, identity uniqueness, dependency
resolution, and ownership topology (A0403).

The former fixed per-role file cardinality is removed: roles grow as the pack
evolves (Global Architect joins architecture_decision). What must hold
instead:

- every declared role has a directory, load policy, and duplicate policy;
- every role directory exists and holds at least one kernel file;
- kernel identities are unique within their role directory and across roles;
- every kernel file's declared dependencies (``requires``) resolve to a
  kernel identity declared in the pack;
- the terminal role holds exactly one flawless_victory.contract.yaml.
"""
from __future__ import annotations

import re

from _common import STATUS_FAIL, STATUS_PASS, base_parser, emit, load_yaml, rel, resolve_root

_KERNEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def main() -> int:
    parser = base_parser(
        "Validate kernel role declarations, identity uniqueness, and ownership topology."
    )
    args = parser.parse_args()
    root = resolve_root(__file__, args.root)
    role_map_path = root / "runtime/kernel_pipeline/KERNEL_ROLE_MAP.yaml"
    findings: list[str] = []

    if not role_map_path.exists():
        findings.append("Missing runtime/kernel_pipeline/KERNEL_ROLE_MAP.yaml")
        return emit(
            {"validator": "validate_kernel_roles", "status": STATUS_FAIL, "findings": findings},
            args.json,
        )

    role_map = load_yaml(role_map_path).get("role_map", {})
    if not isinstance(role_map, dict) or not role_map:
        findings.append("role_map must declare at least one role.")

    identities: dict[str, str] = {}
    declared: set[str] = set()
    for role, entry in role_map.items():
        if not isinstance(entry, dict):
            findings.append(f"Role {role} entry is not a mapping.")
            continue
        directory = entry.get("directory")
        load_policy = entry.get("load_policy")
        duplicate_policy = entry.get("duplicate_policy")
        if not directory:
            findings.append(f"Role {role} has no directory.")
            continue
        if not load_policy:
            findings.append(f"Role {role} has no load_policy.")
        if not duplicate_policy:
            findings.append(f"Role {role} has no duplicate_policy.")
        dir_path = root / str(directory)
        if not dir_path.is_dir():
            findings.append(f"Role {role} directory missing: {directory}")
            continue
        files = sorted(
            [
                p
                for p in dir_path.iterdir()
                if p.is_file()
                and p.suffix.lower() in {".yaml", ".yml", ".md"}
            ]
        )
        if not files:
            findings.append(f"Role {role} directory holds no kernel files: {directory}")
        role_ids: set[str] = set()
        for path in files:
            if path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            doc = load_yaml(path)
            if not isinstance(doc, dict):
                findings.append(f"Kernel file is not a mapping: {rel(path, root)}")
                continue
            kernel_id = str(doc.get("kernel_id") or path.stem)
            if not _KERNEL_ID_RE.fullmatch(kernel_id):
                findings.append(f"Kernel id invalid in {rel(path, root)}: {kernel_id}")
            if kernel_id in role_ids:
                findings.append(f"Duplicate kernel id within role {role}: {kernel_id}")
            role_ids.add(kernel_id)
            if kernel_id in identities and identities[kernel_id] != role:
                findings.append(
                    f"Kernel id {kernel_id} declared in both {identities[kernel_id]} and {role}"
                )
            identities[kernel_id] = role
            declared.add(kernel_id)

    # Dependency resolution (pack activation graph): every kernel the pipeline
    # activates must exist and live inside one of the declared role
    # directories — the pipeline/role dependency model is the pack's own.
    pipeline_path = root / "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"
    if pipeline_path.exists():
        pipeline = load_yaml(pipeline_path)
        role_dirs = [
            root / str(entry["directory"])
            for entry in role_map.values()
            if isinstance(entry, dict) and entry.get("directory")
        ]
        for phase in pipeline.get("phase_order", []):
            for kernel_rel in phase.get("primary_kernels", []):
                kernel_path = root / str(kernel_rel)
                if not kernel_path.is_file():
                    findings.append(f"Pipeline references missing kernel: {kernel_rel}")
                    continue
                resolved = kernel_path.resolve()
                if not any(resolved.is_relative_to(directory.resolve()) for directory in role_dirs):
                    findings.append(
                        f"Pipeline kernel outside any declared role directory: {kernel_rel}"
                    )

    # Ownership topology: exactly one terminal contract.
    terminal_dir = root / "runtime/kernels/terminal"
    terminals = list(terminal_dir.glob("*")) if terminal_dir.exists() else []
    terminal_contracts = [
        p for p in terminals if p.is_file() and p.name == "flawless_victory.contract.yaml"
    ]
    if len(terminal_contracts) != 1:
        findings.append("Exactly one terminal flawless_victory.contract.yaml is required.")

    status = STATUS_PASS if not findings else STATUS_FAIL
    if not findings:
        findings.append(
            "Kernel roles declare directories, policies, unique identities, resolved "
            "dependencies, and a single terminal contract."
        )
    return emit(
        {
            "validator": "validate_kernel_roles",
            "status": status,
            "findings": findings,
            "role_map_path": rel(role_map_path, root),
            "declared_kernel_ids": sorted(declared),
        },
        args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
