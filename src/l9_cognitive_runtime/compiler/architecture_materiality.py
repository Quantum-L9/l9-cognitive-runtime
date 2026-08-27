"""Architecture materiality assessment (GAR activation rule, A0402).

Global Architect activates when architecture materiality is proven by intent
and verified context signals — never from kernel file presence, never from
raw text after typed intent exists. Assessment is deterministic:

- context signals: caller-provided ``source_context.context_signals`` mapped
  through ``context_signal_map`` (verified facts, not prose);
- mission signals: word-boundary token evidence mapped through
  ``mission_signal_tokens``.

Any trigger fires GAR; active lenses are the lens→trigger projections of the
fired triggers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from l9_cognitive_runtime.models import IntentContract


@dataclass(frozen=True)
class ArchitectureMateriality:
    required: bool
    triggers: tuple[str, ...] = ()
    active_lenses: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "triggers": list(self.triggers),
            "active_lenses": list(self.active_lenses),
            "evidence": list(self.evidence),
        }


_NOT_REQUIRED = ArchitectureMateriality(required=False, evidence=())


def _word_evidence(text: str, tokens: list[str]) -> list[str]:
    lowered = text.lower()
    return [token for token in tokens if re.search(rf"\b{re.escape(token)}\b", lowered)]


def assess_materiality(intent: IntentContract, rules: dict[str, Any]) -> ArchitectureMateriality:
    """Deterministic GAR activation assessment from intent + routing rules."""
    materiality_rules = rules.get("architecture_materiality") or {}
    token_map = materiality_rules.get("mission_signal_tokens") or {}
    context_map = materiality_rules.get("context_signal_map") or {}
    lens_map = (materiality_rules.get("gar_activation") or {}).get("lenses") or {}

    source_context = intent.source_context or {}
    raw_signals = source_context.get("context_signals")
    context_signals = raw_signals if isinstance(raw_signals, list) else []

    triggers: set[str] = set()
    evidence: list[str] = []
    for signal in context_signals:
        trigger = context_map.get(str(signal))
        if trigger:
            triggers.add(trigger)
            evidence.append(f"context_signal:{signal}")
    for trigger, tokens in token_map.items():
        hits = _word_evidence(intent.mission, [str(token) for token in tokens])
        if hits:
            triggers.add(trigger)
            evidence.append(f"mission_token:{trigger}:{','.join(sorted(hits))}")

    if not triggers:
        return _NOT_REQUIRED

    active_lenses: list[str] = []
    for lens, lens_triggers in lens_map.items():
        if any(trigger in triggers for trigger in lens_triggers):
            active_lenses.append(lens)

    return ArchitectureMateriality(
        required=True,
        triggers=tuple(sorted(triggers)),
        active_lenses=tuple(active_lenses),
        evidence=tuple(evidence),
    )
