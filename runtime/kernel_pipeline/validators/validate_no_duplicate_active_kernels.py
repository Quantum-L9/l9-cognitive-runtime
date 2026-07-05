#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from _common import STATUS_FAIL, STATUS_PASS, base_parser, emit, kernel_files, parse_kernel_identity, resolve_root


def main() -> int:
    parser = base_parser("Detect duplicate active kernel identities and duplicate terminal contracts.")
    args = parser.parse_args()
    root = resolve_root(__file__, args.root)
    findings: list[str] = []

    identities = [parse_kernel_identity(p, root) for p in kernel_files(root)]
    active = [item for item in identities if item["status"] == "ACTIVE"]

    by_name: dict[str, list[str]] = defaultdict(list)
    for item in active:
        by_name[str(item["name"]).lower()].append(item["path"])

    duplicates = {name: paths for name, paths in by_name.items() if len(paths) > 1}
    for name, paths in sorted(duplicates.items()):
        findings.append(f"Duplicate active kernel identity {name!r}: {paths}")

    terminal_paths = [item["path"] for item in identities if item["path"].startswith("runtime/kernels/terminal/")]
    if terminal_paths != ["runtime/kernels/terminal/flawless_victory.contract.yaml"]:
        findings.append(f"Unexpected terminal contract set: {terminal_paths}")

    if len(active) != 18:
        findings.append(f"Expected 18 active kernels in clean pack, found {len(active)}")

    status = STATUS_PASS if not findings else STATUS_FAIL
    if not findings:
        findings.append("No duplicate active kernel identities detected; terminal contract is singular.")
    return emit({"validator": "validate_no_duplicate_active_kernels", "status": status, "findings": findings, "active_kernel_count": len(active)}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
