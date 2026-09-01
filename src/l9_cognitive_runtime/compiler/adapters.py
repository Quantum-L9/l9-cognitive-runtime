"""Deterministic adapter projections of the canonical execution packet.

Adapters never own runtime law: each adapter payload is a projection of the
packet (A0701) that preserves every blocking obligation, Unknown, validation
requirement, delivery requirement, and architectural constraint (INV-013).
Rendering fails closed when the packet is incomplete or a blocking GAR
architecture obligation is missing (A0702).

The compiled task context travels the same way (INV-CTX-030/031): the adapter
packet carries the **body**, not only the digest, and passes the digest through
unchanged rather than recomputing it. Carrying a digest nothing verifies is
metadata rather than integrity, so ``validate_packet`` recomputes the canonical
digest of the carried body and requires the declared digest and the packet
provenance to agree with it. A mutated body under an unchanged declared digest
therefore fails before any adapter sees it.

Applicable law, authority limits and effective order, capability gaps, and
unresolved context unknowns are projected explicitly as well, so a template can
render them but no template can silently drop them from the packet.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from l9_cognitive_runtime.models.canonical import sha256_digest
from l9_cognitive_runtime.models.errors import InvalidValueError

ADAPTER_TEMPLATE_DIR = "runtime/contract_compiler/adapters"

ADAPTER_TEMPLATES = {
    "claude_code": "claude_code.md",
    "cursor": "cursor.md",
    "codex": "codex.md",
    "chatgpt": "chatgpt.md",
    "human_operator": "human_operator.md",
}


@dataclass(frozen=True)
class AdapterPacket:
    adapter: str
    source_contract: str
    packet_digest: str
    context_digest: str
    compiled_task_context: dict[str, Any]
    content: str
    required_obligation_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    validation_properties: tuple[dict[str, Any], ...]
    delivery_obligations: tuple[dict[str, Any], ...]
    gar_output_refs: tuple[str, ...]
    applicable_law_refs: tuple[str, ...] = ()
    authority_limit_refs: tuple[str, ...] = ()
    capability_gap_refs: tuple[str, ...] = ()
    context_unknown_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "source_contract": self.source_contract,
            "packet_digest": self.packet_digest,
            "context_digest": self.context_digest,
            "compiled_task_context": self.compiled_task_context,
            "content": self.content,
            "required_obligation_ids": list(self.required_obligation_ids),
            "unknowns": list(self.unknowns),
            "validation_properties": list(self.validation_properties),
            "delivery_obligations": list(self.delivery_obligations),
            "gar_output_refs": list(self.gar_output_refs),
            "applicable_law_refs": list(self.applicable_law_refs),
            "authority_limit_refs": list(self.authority_limit_refs),
            "capability_gap_refs": list(self.capability_gap_refs),
            "context_unknown_ids": list(self.context_unknown_ids),
            "limitations": list(self.limitations),
        }


def _packet_digest(packet: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _require_section(packet: dict[str, Any], key: str) -> Any:
    value = packet.get(key)
    if value is None:
        raise InvalidValueError("execution packet section missing", path=key)
    return value


def validate_packet(packet: dict[str, Any]) -> None:
    """Fail closed on an incomplete or weakened packet (INV-013)."""
    _require_section(packet, "intent")
    context_body = _require_section(packet, "compiled_task_context")
    declared_digest = _require_section(packet, "compiled_task_context_digest")
    _require_section(packet, "active_kernel_bindings")
    _require_section(packet, "execution_steps")
    _require_section(packet, "required_obligations")
    _require_section(packet, "validation_properties")
    _require_section(packet, "delivery_obligations")
    _require_section(packet, "unknowns")
    _require_section(packet, "convergence_contract")
    _require_section(packet, "provenance")
    # INV-CTX-030: the packet's context identity is verified against the body it
    # actually carries, not merely echoed. A digest nothing recomputes cannot
    # detect the one failure it exists to detect.
    recomputed = sha256_digest(context_body)
    if recomputed != declared_digest:
        raise InvalidValueError(
            "compiled task context body does not hash to its declared digest",
            path="compiled_task_context",
            details={"declared": declared_digest, "recomputed": recomputed},
        )
    provenance_digest = (packet["provenance"] or {}).get("context_digest")
    if provenance_digest != declared_digest:
        raise InvalidValueError(
            "packet context digest disagrees with packet provenance",
            path="compiled_task_context_digest",
            details={"packet": declared_digest, "provenance": provenance_digest},
        )
    required_ids = {o["obligation_id"] for o in packet["required_obligations"]}
    # Every validation property must bind a required obligation still present,
    # and every required obligation must keep its validation path (INV-013).
    property_refs = {p["obligation_ref"] for p in packet["validation_properties"]}
    foreign_props = property_refs - required_ids
    if foreign_props:
        raise InvalidValueError(
            "validation property binds an obligation absent from the packet",
            path="validation_properties",
            details={"obligation_refs": sorted(foreign_props)},
        )
    unvalidated = required_ids - property_refs
    if unvalidated:
        raise InvalidValueError(
            "required obligation lost its validation path",
            path="required_obligations",
            details={"obligation_ids": sorted(unvalidated)},
        )
    # Every required delivery obligation must remain required.
    for delivery in packet["delivery_obligations"]:
        if delivery.get("required") and delivery["obligation_id"] not in required_ids:
            raise InvalidValueError(
                "required delivery obligation dropped from the packet",
                path="delivery_obligations",
                details={"obligation_id": delivery["obligation_id"]},
            )
    # A0702: a blocking GAR architecture obligation must be present with
    # resolvable GAR output bindings — never omitted, never weakened.
    if "OBL.ARCHITECTURE" in required_ids:
        bindings = packet["active_kernel_bindings"]
        gar = next(
            (
                b
                for b in bindings
                if b.get("source_ref", "").endswith("global_architect_kernel.yaml")
            ),
            None,
        )
        if gar is None:
            raise InvalidValueError(
                "architecture obligation present but GAR binding missing",
                path="active_kernel_bindings",
            )
        if not gar.get("outputs"):
            raise InvalidValueError(
                "GAR binding declares no outputs",
                path="active_kernel_bindings",
            )


def applicable_law_refs(packet: dict[str, Any]) -> tuple[str, ...]:
    """Law identities the compiled context selected, in canonical order."""
    context = packet.get("compiled_task_context") or {}
    return tuple(str(law["law_id"]) for law in context.get("applicable_law") or [])


def authority_limit_refs(packet: dict[str, Any]) -> tuple[str, ...]:
    """Proven authority limits. An adapter may render them; none may drop them."""
    authority = (packet.get("compiled_task_context") or {}).get("authority") or {}
    return tuple(str(fact["authority_id"]) for fact in authority.get("limits") or [])


def capability_gap_refs(packet: dict[str, Any]) -> tuple[str, ...]:
    """Required capabilities the compiled context did not prove available."""
    capabilities = (packet.get("compiled_task_context") or {}).get("capabilities") or {}
    available = {str(fact["capability_id"]) for fact in capabilities.get("available") or []}
    return tuple(
        sorted(
            str(requirement["capability_id"])
            for requirement in capabilities.get("required") or []
            if str(requirement["capability_id"]) not in available
        )
    )


def context_unknown_ids(packet: dict[str, Any]) -> tuple[str, ...]:
    """Every unresolved compiled-context unknown, blocking or not."""
    context = packet.get("compiled_task_context") or {}
    return tuple(str(unknown["unknown_id"]) for unknown in context.get("unresolved_unknowns") or [])


def gar_output_refs(packet: dict[str, Any]) -> tuple[str, ...]:
    bindings = packet.get("active_kernel_bindings") or []
    refs: list[str] = []
    for binding in bindings:
        if binding.get("source_ref", "").endswith("global_architect_kernel.yaml"):
            for output in binding.get("outputs") or []:
                refs.append(output["id"])
    return tuple(sorted(set(refs)))


class AdapterRenderer:
    """Deterministic packet projections per adapter target."""

    def __init__(self, pack_root: Path | None = None) -> None:
        self._pack_root = pack_root

    def render(self, packet: dict[str, Any], adapter: str) -> AdapterPacket:
        validate_packet(packet)
        template_name = ADAPTER_TEMPLATES.get(adapter)
        if template_name is None:
            raise InvalidValueError("unknown adapter target", path=adapter)
        packet_digest = _packet_digest(packet)
        content = self._render_template(template_name, packet, packet_digest)
        required_ids = tuple(sorted(o["obligation_id"] for o in packet["required_obligations"]))
        return AdapterPacket(
            adapter=adapter,
            source_contract="FINAL_EXECUTION_CONTRACT",
            packet_digest=packet_digest,
            # INV-CTX-031: the projection carries the compiled-context identity
            # through unchanged, and the body losslessly beside it. It is never
            # recomputed, reselected, or summarized.
            context_digest=str(packet["compiled_task_context_digest"]),
            compiled_task_context=dict(packet["compiled_task_context"]),
            content=content,
            required_obligation_ids=required_ids,
            unknowns=tuple(str(u) for u in packet["unknowns"]),
            validation_properties=tuple(dict(p) for p in packet["validation_properties"]),
            delivery_obligations=tuple(dict(o) for o in packet["delivery_obligations"]),
            gar_output_refs=gar_output_refs(packet),
            applicable_law_refs=applicable_law_refs(packet),
            authority_limit_refs=authority_limit_refs(packet),
            capability_gap_refs=capability_gap_refs(packet),
            context_unknown_ids=context_unknown_ids(packet),
        )

    def _render_template(self, template_name: str, packet: dict[str, Any], digest: str) -> str:
        """Render the pack template or the deterministic fallback projection."""
        template: str | None = None
        if self._pack_root is not None:
            template_path = self._pack_root / ADAPTER_TEMPLATE_DIR / template_name
            if template_path.is_file():
                template = template_path.read_text(encoding="utf-8")
        if template is None:
            template = DEFAULT_TEMPLATE
        intent = packet["intent"]
        kernels = [binding["source_ref"] for binding in packet["active_kernel_bindings"]]
        obligations = [o["obligation_id"] for o in packet["required_obligations"]]
        delivery = [o["obligation_id"] for o in packet["delivery_obligations"]]
        validation = [p["property_id"] for p in packet["validation_properties"]]
        authority = (packet.get("compiled_task_context") or {}).get("authority") or {}
        placeholders = {
            "{{adapter}}": str(self._adapter_for_template(template_name)),
            "{{packet_digest}}": digest,
            "{{context_digest}}": str(packet["compiled_task_context_digest"]),
            "{{applicable_law}}": "\n".join(f"- {law}" for law in applicable_law_refs(packet)),
            "{{authority_order}}": "\n".join(
                f"- {entry}" for entry in authority.get("effective_order") or []
            ),
            "{{authority_order_source}}": str(authority.get("effective_order_source", "")),
            "{{authority_limits}}": "\n".join(
                f"- {limit}" for limit in authority_limit_refs(packet)
            ),
            "{{capability_gaps}}": "\n".join(f"- {gap}" for gap in capability_gap_refs(packet)),
            "{{context_unknowns}}": "\n".join(
                f"- {unknown}" for unknown in context_unknown_ids(packet)
            ),
            "{{mission}}": str(intent.get("mission", "")),
            "{{realization_mode}}": str(
                intent.get("objective", {}).get("realization_mode", "UNKNOWN")
            ),
            "{{kernel_activation}}": "\n".join(f"- {k}" for k in kernels),
            "{{required_obligations}}": "\n".join(f"- {o}" for o in obligations),
            "{{validation_properties}}": "\n".join(f"- {v}" for v in validation),
            "{{delivery_obligations}}": "\n".join(f"- {d}" for d in delivery),
            "{{unknowns}}": "\n".join(f"- {u}" for u in packet["unknowns"]),
            "{{gar_outputs}}": "\n".join(f"- {r}" for r in gar_output_refs(packet)),
        }
        rendered = template
        for key, value in placeholders.items():
            rendered = rendered.replace(key, value)
        unresolved = [key for key in placeholders if key in rendered]
        if unresolved:
            raise InvalidValueError(
                "adapter template left placeholders unresolved",
                path=template_name,
                details={"placeholders": unresolved},
            )
        return rendered

    @staticmethod
    def _adapter_for_template(template_name: str) -> str:
        return template_name.removesuffix(".md")


DEFAULT_TEMPLATE = """# L9 Cognitive Runtime Execution Packet — {{adapter}} projection

Packet digest: {{packet_digest}}

## Mission
{{mission}} (realization: {{realization_mode}})

## Active kernels
{{kernel_activation}}

## Required obligations (blocking — must not be dropped)
{{required_obligations}}

## Validation properties
{{validation_properties}}

## Delivery obligations
{{delivery_obligations}}

## Unknowns (must be preserved until disposed)
{{unknowns}}

## Global Architect outputs
{{gar_outputs}}

## Compiled task context (digest {{context_digest}})
Projected from the packet's compiled task context. Never re-derived, never reselected.

### Applicable law
{{applicable_law}}

### Effective authority order (source: {{authority_order_source}})
{{authority_order}}

### Authority limits
{{authority_limits}}

### Capability gaps (required, not proven available)
{{capability_gaps}}

### Unresolved context unknowns
{{context_unknowns}}
"""
