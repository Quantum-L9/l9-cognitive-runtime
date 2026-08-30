"""Typed activation planning over the canonical intent contract.

The planner consumes the typed ``IntentContract`` plus pack-resolved routing
rules and pipeline definition — never raw task text as its sole semantic input.
Routing, phase ordering, terminal gating, and kernel selection are the single
authoritative implementation; the legacy ``runtime/kernel_pipeline/planner/
plan_activation.py`` script is a thin CLI wrapper over this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from l9_cognitive_runtime.compiler.architecture_materiality import assess_materiality
from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.context import DiscoveryContext
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.parsing import load_yaml_file

_REQUIRED_PLAN_FIELDS = (
    "task_summary",
    "matched_route",
    "confidence",
    "phase_sequence",
    "active_kernels",
    "skipped_kernels",
    "terminal_allowed",
    "required_outputs",
    "blockers",
    "unknowns",
    "next_phase",
    "architecture_materiality",
)


@dataclass(frozen=True)
class ActivationPlan:
    task_summary: str
    matched_route: str
    confidence: str
    phase_sequence: list[str]
    active_kernels: list[str]
    skipped_kernels: list[str]
    terminal_allowed: bool
    required_outputs: list[str]
    blockers: list[str]
    unknowns: list[str]
    next_phase: str
    architecture_materiality: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ActivationPlan:
        """Reconstruct a typed plan from a KERNEL_ACTIVATION_PLAN.yaml mapping.

        Fails closed on missing required fields — a partial plan is never a
        valid activation input (no silent default-kernel fallback).
        """
        missing = [field for field in _REQUIRED_PLAN_FIELDS if field not in data]
        if missing:
            raise InvalidValueError(
                "activation plan missing required fields",
                path="activation_plan",
                details={"missing": missing},
            )
        materiality = data.get("architecture_materiality") or {}
        return cls(
            task_summary=str(data["task_summary"]),
            matched_route=str(data["matched_route"]),
            confidence=str(data["confidence"]),
            phase_sequence=[str(item) for item in data["phase_sequence"]],
            active_kernels=[str(item) for item in data["active_kernels"]],
            skipped_kernels=[str(item) for item in data["skipped_kernels"]],
            terminal_allowed=bool(data["terminal_allowed"]),
            required_outputs=[str(item) for item in data["required_outputs"]],
            blockers=[str(item) for item in data["blockers"]],
            unknowns=[str(item) for item in data["unknowns"]],
            next_phase=str(data["next_phase"]),
            architecture_materiality=dict(materiality),
        )

    def to_dict(self) -> dict[str, Any]:
        """Emit the ACTIVATION_PLAN_SCHEMA-shaped mapping used by CLI output."""
        return {
            "task_summary": self.task_summary,
            "matched_route": self.matched_route,
            "confidence": self.confidence,
            "phase_sequence": list(self.phase_sequence),
            "active_kernels": list(self.active_kernels),
            "skipped_kernels": list(self.skipped_kernels),
            "terminal_allowed": self.terminal_allowed,
            "required_outputs": list(self.required_outputs),
            "blockers": list(self.blockers),
            "unknowns": list(self.unknowns),
            "next_phase": self.next_phase,
            "architecture_materiality": dict(self.architecture_materiality),
        }


class ActivationPlanner:
    """Deterministic phase/kernel selection from typed intent + pack rules."""

    def plan(
        self,
        intent: IntentContract,
        *,
        rules_path: Path,
        pipeline_path: Path,
        include_terminal: bool = False,
        discovery: DiscoveryContext | None = None,
    ) -> ActivationPlan:
        pipeline = load_yaml_file(pipeline_path)
        rules = load_yaml_file(rules_path)
        phases_by_id = self._phase_map(pipeline)
        route_name, route, confidence = self._match_route(intent.mission, rules)

        # A0402/INV-CTX-014: Global Architect activates from architecture
        # materiality — proven intent plus *governed* discovery signals — never
        # from file presence and never from a raw caller hint.
        materiality = assess_materiality(intent, rules, discovery)
        materiality_dict = materiality.to_dict()

        phases = list(route.get("phases", []))
        if include_terminal:
            phases.append("P7_FLAWLESS_VICTORY")
        else:
            for optional in route.get("optional_phases", []):
                if optional in {
                    "P4_ALIGNMENT_AND_STUB_GATE",
                    "P5_RECURSIVE_IMPROVEMENT",
                    "P6_LEVERAGE_COMPRESSION",
                }:
                    if any(
                        token in intent.mission.lower()
                        for token in [
                            "clean",
                            "dedupe",
                            "streamline",
                            "improve",
                            "harden",
                            "stubs",
                            "gaps",
                            "leverage",
                        ]
                    ):
                        phases.append(optional)

        # GAR materiality pulls the architecture phase into the sequence.
        gar_activation = (rules.get("architecture_materiality") or {}).get("gar_activation") or {}
        if materiality.required and gar_activation.get("adds_phase") not in phases:
            phases.append(str(gar_activation["adds_phase"]))

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
        insert_after: list[str] = []
        for kernel in route.get("task_kernels", []):
            if kernel not in active:
                insert_after.append(kernel)
        if insert_after:
            last_constitutional_index = -1
            for idx, kernel in enumerate(active):
                if "/constitutional/" in kernel:
                    last_constitutional_index = idx
            insert_at = (
                last_constitutional_index + 1 if last_constitutional_index >= 0 else len(active)
            )
            active = active[:insert_at] + insert_after + active[insert_at:]

        term_allowed = self._terminal_allowed(intent.mission, phases, rules) or include_terminal
        if "P7_FLAWLESS_VICTORY" in phases and not term_allowed:
            phases.remove("P7_FLAWLESS_VICTORY")
            active = [k for k in active if not k.endswith("flawless_victory.contract.yaml")]

        required_outputs: list[str] = []
        for phase_id in phases:
            for output in phases_by_id.get(phase_id, {}).get("required_outputs", []):
                if output not in required_outputs:
                    required_outputs.append(output)

        skipped = [k for k in self._all_kernel_paths(pipeline) if k not in active]
        blockers: list[str] = []
        unknowns: list[str] = []
        if confidence == "low":
            unknowns.append(
                "Task route matched only default route; inspect task context before execution."
            )
        if "P1_CONSTITUTIONAL_PREFLIGHT" not in phases and any(
            token in intent.mission.lower()
            for token in ["l9", "kernel", "runtime", "transportpacket", "gate"]
        ):
            blockers.append("L9-related task without constitutional preflight.")

        return ActivationPlan(
            task_summary=intent.mission,
            matched_route=route_name,
            confidence=confidence,
            phase_sequence=phases,
            active_kernels=active,
            skipped_kernels=skipped,
            terminal_allowed=bool(term_allowed and "P7_FLAWLESS_VICTORY" in phases),
            required_outputs=required_outputs,
            blockers=blockers,
            unknowns=unknowns,
            next_phase=phases[0] if phases else "BLOCKED",
            architecture_materiality=materiality_dict,
        )

    @staticmethod
    def _phase_map(pipeline: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {phase["id"]: phase for phase in pipeline.get("phase_order", [])}

    @staticmethod
    def _all_kernel_paths(pipeline: dict[str, Any]) -> list[str]:
        seen: list[str] = []
        for phase in pipeline.get("phase_order", []):
            for kernel in phase.get("primary_kernels", []):
                if kernel not in seen:
                    seen.append(kernel)
        return seen

    @staticmethod
    def _match_route(task: str, rules: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        lowered = task.lower()
        best_name = "pack_review"
        best_route = rules["task_routes"][best_name]
        best_score = -1
        for name, route in rules.get("task_routes", {}).items():
            score = 0
            for token in route.get("match_any", []):
                # Word-boundary matching keeps route selection precise
                # ("add" must not match "address").
                if re.search(rf"\b{re.escape(str(token).lower())}\b", lowered):
                    score += 1
            if score > best_score:
                best_name = name
                best_route = route
                best_score = score
        confidence = "high" if best_score >= 2 else "medium" if best_score == 1 else "low"
        return best_name, best_route, confidence

    @staticmethod
    def _terminal_allowed(task: str, phases: list[str], rules: dict[str, Any]) -> bool:
        lowered = task.lower()
        allowed_phrases = [
            s.lower() for s in rules.get("terminal_activation", {}).get("allowed_when_any", [])
        ]
        return "P7_FLAWLESS_VICTORY" in phases and any(
            phrase in lowered for phrase in allowed_phrases
        )
