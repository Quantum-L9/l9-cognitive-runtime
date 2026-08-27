"""Provider capability/obligation acceptance (A0704).

A capable downstream host accepts obligations explicitly. Required
obligations a provider does not support prevent execution or create a
governed handoff/block — partial acceptance of the required set is never
silent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from l9_cognitive_runtime.models import (
    ObligationDisposition,
)
from l9_cognitive_runtime.models.errors import InvalidValueError


@dataclass(frozen=True)
class ProviderAcceptance:
    provider_id: str
    accepted_obligation_ids: tuple[str, ...]
    unsupported_obligation_ids: tuple[str, ...]
    capabilities: tuple[str, ...]
    authority_limits: tuple[str, ...]
    receipt_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "accepted_obligation_ids": list(self.accepted_obligation_ids),
            "unsupported_obligation_ids": list(self.unsupported_obligation_ids),
            "capabilities": list(self.capabilities),
            "authority_limits": list(self.authority_limits),
            "receipt_digest": self.receipt_digest,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ProviderAcceptance:
        required = (
            "provider_id",
            "accepted_obligation_ids",
            "unsupported_obligation_ids",
            "capabilities",
            "authority_limits",
            "receipt_digest",
        )
        missing = [field for field in required if field not in data]
        if missing:
            raise InvalidValueError(
                "provider acceptance missing required fields",
                path="provider_acceptance",
                details={"missing": missing},
            )
        return cls(
            provider_id=str(data["provider_id"]),
            accepted_obligation_ids=tuple(str(i) for i in data["accepted_obligation_ids"]),
            unsupported_obligation_ids=tuple(str(i) for i in data["unsupported_obligation_ids"]),
            capabilities=tuple(str(i) for i in data["capabilities"]),
            authority_limits=tuple(str(i) for i in data["authority_limits"]),
            receipt_digest=str(data["receipt_digest"]),
        )


def acceptance_receipt_digest(packet: dict[str, Any], acceptance: ProviderAcceptance) -> str:
    payload = {
        "packet_digest": hashlib.sha256(
            json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "provider_id": acceptance.provider_id,
        "accepted_obligation_ids": sorted(acceptance.accepted_obligation_ids),
        "capabilities": sorted(acceptance.capabilities),
        "authority_limits": sorted(acceptance.authority_limits),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def validate_provider_acceptance(
    packet: dict[str, Any],
    acceptance: ProviderAcceptance,
) -> dict[str, Any]:
    """A required unsupported obligation blocks execution (A0704)."""
    required_ids = {
        o["obligation_id"] for o in packet.get("required_obligations") or []
    }
    accepted = set(acceptance.accepted_obligation_ids)
    unsupported = set(acceptance.unsupported_obligation_ids)
    overlap = accepted & unsupported
    if overlap:
        raise InvalidValueError(
            "obligation both accepted and unsupported",
            path="provider_acceptance",
            details={"obligation_ids": sorted(overlap)},
        )
    expected_digest = acceptance_receipt_digest(packet, acceptance)
    if acceptance.receipt_digest != expected_digest:
        raise InvalidValueError(
            "provider acceptance receipt digest mismatch",
            path="provider_acceptance",
            details={"expected": expected_digest, "got": acceptance.receipt_digest},
        )
    blocking = sorted(required_ids & unsupported)
    governed_handoff = [
        o for o in packet.get("required_obligations") or [] if o["obligation_id"] in blocking
    ]
    if blocking:
        return {
            "executable": False,
            "block": {
                "type": "CAPABILITY",
                "unsupported_required_obligation_ids": blocking,
                "governed_handoff": governed_handoff,
                "disposition": ObligationDisposition.VALID_BLOCK.value,
            },
        }
    unaccepted = sorted(required_ids - accepted - unsupported)
    if unaccepted:
        raise InvalidValueError(
            "required obligations neither accepted nor declared unsupported",
            path="provider_acceptance",
            details={"obligation_ids": unaccepted},
        )
    return {
        "executable": True,
        "accepted_obligation_ids": sorted(accepted),
        "receipt_digest": acceptance.receipt_digest,
    }
