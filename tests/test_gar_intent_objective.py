"""PHASE-02 gate evidence: intent & objective strengthening.

Covers L9CR.GAR.PHASE2.INTEGRATION.001 PHASE-02:

- A0201: mixed analyze-and-fix / audit-and-repair intent retains MUTATION.
- A0202: delivery obligation derives from the explicit requested outcome and
  is not inferred away before delivery.
- A0203: UNKNOWN realization stays visible (unknowns) and conservative
  (validation required).
- A0204: Pydantic extra=forbid preserved.
- Gate: typed model matches schema; ObjectiveDeriver is the single owner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate  # type: ignore[import-untyped]

from l9_cognitive_runtime.compiler import ObjectiveDeriver
from l9_cognitive_runtime.models import DeliveryMode, IntentContract, RealizationMode
from l9_cognitive_runtime.models.errors import UnknownFieldError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest
from l9_cognitive_runtime.types import CompileRequest as Request

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "intent_contract.schema.json"


def _derive(mission: str) -> IntentContract:
    return ObjectiveDeriver().derive(Request(mission=mission))


def test_analysis_mission_derives_analysis() -> None:
    intent = _derive("Audit this repository.")
    assert intent.objective.realization_mode is RealizationMode.ANALYSIS
    assert intent.objective.validation_required is False
    assert intent.objective.delivery_required is False
    assert intent.objective.delivery_mode is DeliveryMode.NONE


def test_mixed_analysis_mutation_retains_mutation() -> None:
    # A0201: audit-and-fix / analyze-and-repair deterministically retains MUTATION.
    for mission in (
        "Audit and fix this repository.",
        "Analyze the build system and repair it.",
        "Audit the payment worker and fix the retry bug.",
    ):
        intent = _derive(mission)
        assert intent.objective.realization_mode is RealizationMode.MUTATION, mission


def test_mutation_mission_derives_workspace_delivery() -> None:
    # A0202: delivery obligation derives from the explicit requested outcome.
    intent = _derive("Add safe retry behavior to this asynchronous payment worker.")
    assert intent.objective.realization_mode is RealizationMode.MUTATION
    assert intent.objective.delivery_required is True
    assert intent.objective.delivery_mode is DeliveryMode.IN_PLACE_WORKSPACE
    assert intent.objective.validation_required is True
    assert intent.accountability.required is True


def test_analysis_mission_has_no_delivery_obligation() -> None:
    intent = _derive("Review the deployment configuration.")
    assert intent.objective.delivery_required is False
    assert intent.objective.delivery_mode is DeliveryMode.NONE
    assert intent.accountability.required is False


def test_unknown_realization_stays_visible_and_conservative() -> None:
    # A0203: UNKNOWN realization remains in unknowns and requires validation.
    intent = _derive("Ponder the flux capacitor.")
    assert intent.objective.realization_mode is RealizationMode.UNKNOWN
    assert intent.unknowns is not None
    assert "realization_mode_UNKNOWN" in intent.unknowns
    assert intent.objective.validation_required is True


def test_unknown_realization_does_not_fabricate_delivery() -> None:
    intent = _derive("Contemplate the architecture.")
    assert intent.objective.delivery_required is False
    assert intent.objective.delivery_mode is DeliveryMode.NONE


def test_intent_digest_differs_for_materially_different_missions() -> None:
    audit = _derive("Audit this repository.")
    fix = _derive("Audit and fix this repository.")
    assert audit.sha256() != fix.sha256()
    assert audit.objective.realization_mode is not fix.objective.realization_mode


def test_model_matches_schema() -> None:
    """Gate: typed_model_matches_schema — canonical intent validates against
    the published schema and the schema rejects unknown fields (extra=forbid
    parity, A0204)."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for mission in (
        "Audit this repository.",
        "Audit and fix this repository.",
        "Add safe retry behavior to this asynchronous payment worker.",
        "Ponder the flux capacitor.",
    ):
        intent = _derive(mission)
        validate(instance=intent.to_canonical_dict(), schema=schema)
    with pytest.raises(Exception, match="not_in_schema"):
        validate(
            instance={
                **_derive("Audit this repository.").to_canonical_dict(),
                "not_in_schema": True,
            },
            schema=schema,
        )


def test_extra_forbid_preserved_a0204() -> None:
    from l9_cognitive_runtime.models import IntentContract

    with pytest.raises(UnknownFieldError):
        IntentContract.from_mapping(
            {
                **_derive("Audit this repository.").to_canonical_dict(),
                "bogus": "nope",
            }
        )


def test_service_bundle_intent_carries_objective(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    assert bundle.intent.objective.realization_mode is RealizationMode.MUTATION
    assert bundle.intent.objective.delivery_required is True
