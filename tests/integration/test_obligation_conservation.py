"""LIVE-006: dropping a required obligation between IRs fails compilation."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.compiler.obligations import conserve
from l9_cognitive_runtime.models.errors import ModelValidationError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def test_live006_dropped_obligation_between_execution_and_graph_fails(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    execution_obligations = list(bundle.execution.obligations)
    assert any(o.obligation_id == "OBL.DELIVERY" for o in execution_obligations)
    # Simulate an IR handoff that silently dropped one required obligation.
    dropped = [o for o in execution_obligations if o.obligation_id != "OBL.DELIVERY"]
    with pytest.raises(ModelValidationError, match="disappeared"):
        conserve(bundle.intent.obligations, dropped, stage="execution->graph")


def test_live006_conservation_holds_across_the_live_spine(valid_pack: Path) -> None:
    bundle = CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )
    execution_ids = {o.obligation_id for o in bundle.execution.obligations}
    handoff_ids = {o.obligation_id for o in bundle.handoff.obligations}
    graph_ids = set(bundle.graph.obligation_refs)
    property_refs = {p.obligation_ref for p in bundle.validation.validation_properties}
    required = {o.obligation_id for o in bundle.execution.obligations if o.required}
    assert execution_ids == handoff_ids
    assert required == graph_ids
    assert required <= property_refs
