"""PHASE-03 gate evidence: obligation conservation (INV-003).

Covers L9CR.GAR.PHASE2.INTEGRATION.001 PHASE-03:

- A0301: ExecutionContract carries typed obligations.
- A0302: ValidationContract properties are bound to obligation_id.
- A0303: HandoffContract preserves unresolved obligations + disposition.
- A0304: conservation validation between IRs.
- Gate: no required obligation disappears, no duplicate ids, owners resolve,
  consumers exist, terminal dispositions are legal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.compiler.obligations import (
    RESERVED_OWNERS,
    conserve,
    conserve_ids,
    validate_obligations,
)
from l9_cognitive_runtime.models import (
    Obligation,
    ObligationDisposition,
    ObligationKind,
)
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def _obligation(obligation_id: str, **overrides: object) -> Obligation:
    data: dict[str, object] = {
        "obligation_id": obligation_id,
        "kind": ObligationKind.REALIZATION,
        "source_ref": "intent:i1",
        "required": True,
        "owner": "objective_deriver",
        "consumer_refs": ["execution_graph"],
        "evidence_requirements": ["evidence"],
        "disposition": ObligationDisposition.PENDING,
    }
    data.update(overrides)
    return Obligation.from_mapping(data)


def test_live_bundle_conserves_obligations(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    intent_ids = {o.obligation_id for o in bundle.intent.obligations}
    execution_ids = {o.obligation_id for o in bundle.execution.obligations}
    handoff_ids = {o.obligation_id for o in bundle.handoff.obligations}
    required_pending = {
        o.obligation_id
        for o in bundle.execution.obligations
        if o.required and o.disposition is ObligationDisposition.PENDING
    }
    # A0301: execution carries the intent-derived obligations.
    assert intent_ids == execution_ids
    # A0303: handoff preserves every obligation with its disposition.
    assert execution_ids == handoff_ids
    # Graph carries the required pending ids.
    assert set(bundle.graph.obligation_refs) == required_pending
    # A0302: every required obligation has exactly one bound validation property.
    property_refs = [p.obligation_ref for p in bundle.validation.validation_properties]
    assert set(property_refs) == required_pending
    assert len(property_refs) == len(set(property_refs))


def test_mission_semantics_change_obligation_set(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    audit = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    fix = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    audit_ids = {o.obligation_id for o in audit.execution.obligations}
    fix_ids = {o.obligation_id for o in fix.execution.obligations}
    # MUTATION derives DELIVERY; ANALYSIS does not.
    assert "OBL.DELIVERY" in fix_ids
    assert "OBL.DELIVERY" not in audit_ids
    assert audit.validation.sha256() != fix.validation.sha256()
    assert audit.handoff.sha256() != fix.handoff.sha256()


def test_required_obligation_disappearance_fails() -> None:
    parent = [_obligation("OBL.REALIZATION")]
    with pytest.raises(InvalidValueError, match="disappeared"):
        conserve(parent, [], stage="test->test+1")


def test_duplicate_obligation_id_fails() -> None:
    parent = [_obligation("OBL.REALIZATION"), _obligation("OBL.REALIZATION")]
    with pytest.raises(InvalidValueError, match="duplicate"):
        conserve(parent, parent, stage="test->test+1")


def test_silent_kind_renaming_fails() -> None:
    parent = [_obligation("OBL.REALIZATION")]
    child = [_obligation("OBL.REALIZATION", kind=ObligationKind.DELIVERY)]
    with pytest.raises(InvalidValueError, match="kind changed"):
        conserve(parent, child, stage="test->test+1")


def test_terminal_disposition_permits_absence() -> None:
    parent = [_obligation("OBL.DELIVERY", disposition=ObligationDisposition.SATISFIED)]
    conserve(parent, [], stage="test->test+1")


def test_terminal_disposition_permits_valid_block() -> None:
    parent = [_obligation("OBL.REALIZATION", disposition=ObligationDisposition.VALID_BLOCK)]
    conserve(parent, [], stage="test->test+1")


def test_unresolvable_owner_fails() -> None:
    bad = _obligation("OBL.REALIZATION", owner="no_such_kernel")
    with pytest.raises(InvalidValueError, match="owner"):
        validate_obligations([bad], set(RESERVED_OWNERS), stage="intent")


def test_required_obligation_without_consumer_fails() -> None:
    bad = _obligation("OBL.REALIZATION", consumer_refs=[])
    with pytest.raises(InvalidValueError, match="consumer"):
        validate_obligations([bad], set(RESERVED_OWNERS), stage="intent")


def test_conserve_ids_rejects_foreign_and_duplicate_child_ids() -> None:
    parent = [_obligation("OBL.REALIZATION")]
    with pytest.raises(InvalidValueError, match="absent"):
        conserve_ids(parent, ["OBL.REALIZATION", "OBL.FOREIGN"], stage="execution->validation")
    with pytest.raises(InvalidValueError, match="duplicate"):
        conserve_ids(parent, ["OBL.REALIZATION", "OBL.REALIZATION"], stage="x->y")


def test_unknown_realization_derives_blocking_epistemic_obligation(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(mission="Ponder the flux capacitor.", pack_root=valid_pack)
    )
    ids = {o.obligation_id for o in bundle.execution.obligations}
    assert "OBL.EPISTEMIC.REALIZATION_RESOLUTION" in ids
    epistemic = next(
        o
        for o in bundle.execution.obligations
        if o.obligation_id == "OBL.EPISTEMIC.REALIZATION_RESOLUTION"
    )
    assert epistemic.required is True
    assert epistemic.disposition is ObligationDisposition.PENDING
