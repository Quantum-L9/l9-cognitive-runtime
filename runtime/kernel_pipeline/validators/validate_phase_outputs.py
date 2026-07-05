#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from _common import STATUS_FAIL, STATUS_PASS, emit, load_yaml, resolve_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate phase output contracts against pipeline declarations and, optionally, an outputs directory.")
    parser.add_argument("--root", default=None, help="Pack root. Defaults to validator-relative pack root.")
    parser.add_argument("--outputs-dir", default=None, help="Optional directory containing generated phase outputs to check for presence.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()
    root = resolve_root(__file__, args.root)
    findings: list[str] = []

    pipeline_path = root / "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"
    contracts_path = root / "runtime/kernel_pipeline/PHASE_OUTPUT_CONTRACTS.yaml"
    if not pipeline_path.exists():
        findings.append("Missing KERNEL_PIPELINE.yaml")
    if not contracts_path.exists():
        findings.append("Missing PHASE_OUTPUT_CONTRACTS.yaml")
    if findings:
        return emit({"validator": "validate_phase_outputs", "status": STATUS_FAIL, "findings": findings}, args.json)

    pipeline = load_yaml(pipeline_path)
    contracts_doc = load_yaml(contracts_path)
    contracts = contracts_doc.get("phase_output_contracts", {})

    for phase in pipeline.get("phase_order", []):
        phase_id = phase.get("id")
        required = phase.get("required_outputs", [])
        declared = contracts.get(phase_id)
        if declared != required:
            findings.append(f"{phase_id} output contract mismatch: pipeline={required}, contracts={declared}")

    allowed_status = contracts_doc.get("validation_status_values", [])
    required_status = ["passed", "failed", "blocked", "unknown", "not_applicable_with_reason"]
    if allowed_status != required_status:
        findings.append(f"validation_status_values must be {required_status}, found {allowed_status}")

    if args.outputs_dir:
        outputs_dir = Path(args.outputs_dir).resolve()
        if not outputs_dir.exists():
            findings.append(f"outputs-dir does not exist: {outputs_dir}")
        else:
            for phase_id, output_names in contracts.items():
                for output_name in output_names:
                    if not (outputs_dir / output_name).exists():
                        findings.append(f"Missing generated output for {phase_id}: {output_name}")

    status = STATUS_PASS if not findings else STATUS_FAIL
    if not findings:
        msg = "Phase output declarations match pipeline."
        if args.outputs_dir:
            msg += " Generated output files are present."
        findings.append(msg)
    return emit({"validator": "validate_phase_outputs", "status": status, "findings": findings}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
