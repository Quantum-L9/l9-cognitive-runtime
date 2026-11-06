# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_integration_test_semantic_propagation__py
# title: test semantic propagation
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/integration/test_semantic_propagation.py
# content_hash: 9d8e9d7114b654bef0bb04a9d96374bf867ca70fe15b8261ef4563c5c03562e9
# token_cost_estimate: 382
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""LIVE-001: material intent differences propagate through every IR."""

from __future__ import annotations

from pathlib import Path

from l9_cognitive_runtime.models import RealizationMode
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def test_live001_audit_vs_audit_and_fix_propagate_semantics(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    audit = service.compile_runtime(
        CompileRequest(mission="Audit this repository.", pack_root=valid_pack)
    )
    fix = service.compile_runtime(
        CompileRequest(mission="Audit and fix this repository.", pack_root=valid_pack)
    )

    assert audit.intent.objective.realization_mode is RealizationMode.ANALYSIS
    assert fix.intent.objective.realization_mode is RealizationMode.MUTATION

    audit_digests = audit.digests()
    fix_digests = fix.digests()
    assert audit_digests["execution"] != fix_digests["execution"]
    assert audit_digests["graph"] != fix_digests["graph"]
    assert audit_digests["semantic"] != fix_digests["semantic"]

    # Adapter packets project the differing semantics.
    from l9_cognitive_runtime.compiler.adapters import AdapterRenderer

    audit_packet = AdapterRenderer().render(audit.packet, "cursor")
    fix_packet = AdapterRenderer().render(fix.packet, "cursor")
    assert audit_packet.packet_digest != fix_packet.packet_digest
    assert "OBL.DELIVERY" in fix_packet.required_obligation_ids
    assert "OBL.DELIVERY" not in audit_packet.required_obligation_ids
