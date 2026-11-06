#!/usr/bin/env python3
# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.runtime_kernel_pipeline_validators_validate_no_duplicate_active_kernels__py
# title: validate no duplicate active kernels
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: runtime/kernel_pipeline/validators/validate_no_duplicate_active_kernels.py
# content_hash: 6a3465686760af41266e5402637d1e6c9ea5a45eedc58329215ca94629db7193
# token_cost_estimate: 438
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
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
