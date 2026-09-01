"""Architecture materiality assessment (GAR activation rule, A0402, INV-CTX-014).

Global Architect activates when architecture materiality is proven by intent
and *governed* context signals — never from kernel file presence, never from
raw text after typed intent exists. Assessment is deterministic:

- context signals: governed architecture signals proven by the typed
  ``DiscoveryContext``, mapped through ``context_signal_map``. A caller-supplied
  ``source_context.context_signals`` list is **not** consulted: under
  INV-CTX-006 a raw hint cannot by itself establish a fact about the world
  outside the request. To prove a signal, a host supplies a provenance-backed
  ``GovernedConstraint`` whose ``constraint_id`` is the signal name; every entry
  in ``discovery.architecture_signal_refs`` traces to a discovery item whose
  digest is recorded in ``discovery.selected_item_digests``;
- mission signals: word-boundary token evidence mapped through
  ``mission_signal_tokens``. Mission text remains a legitimate *candidate*
  signal — it is the caller stating their own intent, not asserting an external
  fact.

Any trigger fires GAR; active lenses are the lens→trigger projections of the
fired triggers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from l9_cognitive_runtime.models import IntentContract
from l9_cognitive_runtime.models.context import DiscoveryContext


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


def assess_materiality(
    intent: IntentContract,
    rules: dict[str, Any],
    discovery: DiscoveryContext,
) -> ArchitectureMateriality:
    """Deterministic GAR activation from intent + routing rules + governed discovery.

    ``discovery`` is required, not optional. Defaulting it would reintroduce a
    path where materiality is assessed with no governed plane at all, which is
    the shape a caller hint used to slip through.
    """
    materiality_rules = rules.get("architecture_materiality") or {}
    token_map = materiality_rules.get("mission_signal_tokens") or {}
    context_map = materiality_rules.get("context_signal_map") or {}
    lens_map = (materiality_rules.get("gar_activation") or {}).get("lenses") or {}

    triggers: set[str] = set()
    evidence: list[str] = []
    for signal in discovery.architecture_signal_refs:
        trigger = context_map.get(str(signal))
        if trigger:
            triggers.add(trigger)
            evidence.append(f"governed_signal:{signal}")
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
