#!/usr/bin/env python3
"""Kernel activation planner for the clean L9 Cognitive Runtime kernel pack.

This planner is intentionally deterministic: it maps task text to the smallest
valid phase and kernel set using TASK_ROUTING_RULES.yaml plus KERNEL_PIPELINE.yaml.
It does not execute kernels; it emits KERNEL_ACTIVATION_PLAN.yaml content.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
PIPELINE_PATH = ROOT / "runtime" / "kernel_pipeline" / "KERNEL_PIPELINE.yaml"
RULES_PATH = Path(__file__).resolve().parent / "TASK_ROUTING_RULES.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def phase_map(pipeline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {phase["id"]: phase for phase in pipeline.get("phase_order", [])}


def all_kernel_paths(pipeline: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for phase in pipeline.get("phase_order", []):
        for kernel in phase.get("primary_kernels", []):
            if kernel not in seen:
                seen.append(kernel)
    return seen


def match_route(task: str, rules: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    lowered = task.lower()
    best_name = "pack_review"
    best_route = rules["task_routes"][best_name]
    best_score = -1
    for name, route in rules.get("task_routes", {}).items():
        score = 0
        for token in route.get("match_any", []):
            if str(token).lower() in lowered:
                score += 1
        if score > best_score:
            best_name = name
            best_route = route
            best_score = score
    confidence = "high" if best_score >= 2 else "medium" if best_score == 1 else "low"
    return best_name, best_route, confidence


def terminal_allowed(task: str, phases: list[str], rules: dict[str, Any]) -> bool:
    lowered = task.lower()
    allowed_phrases = [s.lower() for s in rules.get("terminal_activation", {}).get("allowed_when_any", [])]
    return "P7_FLAWLESS_VICTORY" in phases and any(phrase in lowered for phrase in allowed_phrases)


def build_plan(task: str, include_terminal: bool = False) -> dict[str, Any]:
    pipeline = load_yaml(PIPELINE_PATH)
    rules = load_yaml(RULES_PATH)
    phases_by_id = phase_map(pipeline)
    route_name, route, confidence = match_route(task, rules)

    phases = list(route.get("phases", []))
    if include_terminal:
        phases.append("P7_FLAWLESS_VICTORY")
    else:
        for optional in route.get("optional_phases", []):
            if optional in {"P4_ALIGNMENT_AND_STUB_GATE", "P5_RECURSIVE_IMPROVEMENT", "P6_LEVERAGE_COMPRESSION"}:
                if any(token in task.lower() for token in ["clean", "dedupe", "streamline", "improve", "harden", "stubs", "gaps", "leverage"]):
                    phases.append(optional)

    # Preserve canonical order and remove duplicates.
    canonical_order = [phase["id"] for phase in pipeline.get("phase_order", [])]
    phases = [phase for phase in canonical_order if phase in set(phases)]

    active: list[str] = []
    for phase_id in phases:
        phase = phases_by_id.get(phase_id, {})
        for kernel in phase.get("primary_kernels", []):
            if phase_id == "P2_TASK_ROUTING":
                continue
            if kernel not in active:
                active.append(kernel)

    # P2 task kernels are selected from route, not all P2 kernels.
    insert_after = []
    for kernel in route.get("task_kernels", []):
        if kernel not in active:
            insert_after.append(kernel)
    if insert_after:
        # Place selected task kernels after the last constitutional kernel when present.
        last_constitutional_index = -1
        for idx, kernel in enumerate(active):
            if "/constitutional/" in kernel:
                last_constitutional_index = idx
        insert_at = last_constitutional_index + 1 if last_constitutional_index >= 0 else len(active)
        active = active[:insert_at] + insert_after + active[insert_at:]

    term_allowed = terminal_allowed(task, phases, rules) or include_terminal
    if "P7_FLAWLESS_VICTORY" in phases and not term_allowed:
        phases.remove("P7_FLAWLESS_VICTORY")
        active = [k for k in active if not k.endswith("flawless_victory.contract.yaml")]

    required_outputs: list[str] = []
    for phase_id in phases:
        for output in phases_by_id.get(phase_id, {}).get("required_outputs", []):
            if output not in required_outputs:
                required_outputs.append(output)

    skipped = [k for k in all_kernel_paths(pipeline) if k not in active]
    blockers: list[str] = []
    unknowns: list[str] = []
    if confidence == "low":
        unknowns.append("Task route matched only default route; inspect task context before execution.")
    if "P1_CONSTITUTIONAL_PREFLIGHT" not in phases and any(token in task.lower() for token in ["l9", "kernel", "runtime", "transportpacket", "gate"]):
        blockers.append("L9-related task without constitutional preflight.")

    return {
        "task_summary": task,
        "matched_route": route_name,
        "confidence": confidence,
        "phase_sequence": phases,
        "active_kernels": active,
        "skipped_kernels": skipped,
        "terminal_allowed": bool(term_allowed and "P7_FLAWLESS_VICTORY" in phases),
        "required_outputs": required_outputs,
        "blockers": blockers,
        "unknowns": unknowns,
        "next_phase": phases[0] if phases else "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a kernel activation plan.")
    parser.add_argument("task", help="Task or objective to route.")
    parser.add_argument("--terminal", action="store_true", help="Allow terminal Flawless Victory when route supports it.")
    parser.add_argument("--out", default=None, help="Optional output path for KERNEL_ACTIVATION_PLAN.yaml")
    args = parser.parse_args()
    plan = build_plan(args.task, include_terminal=args.terminal)
    text = yaml.safe_dump(plan, sort_keys=False, allow_unicode=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 1 if plan["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
