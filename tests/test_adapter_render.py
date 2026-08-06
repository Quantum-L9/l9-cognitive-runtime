"""Golden semantic-equivalence tests for adapter renderers (L9CR-MCP-016)."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.adapters import RENDERERS, render_bundle
from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return CognitiveRuntimeService().compile_runtime(
        CompileRequest(mission="adapter render golden", pack_root=ROOT)
    )


def test_runtime_render_tool_registered() -> None:
    assert "runtime_render" in READ_ONLY_TOOLS
    names = set(build_server(ROOT)._tool_manager._tools.keys())  # noqa: SLF001
    assert "runtime_render" in names


def test_semantic_equivalence_across_targets(bundle) -> None:
    digests = bundle.digests()
    cores = []
    for target in ("generic_mcp", "claude_code", "cursor"):
        rendered = render_bundle(bundle, target, RENDERERS)
        assert rendered.payload["source_bundle_digests"] == digests
        assert rendered.payload["planning"] is False
        assert rendered.payload["execution"] is False
        assert rendered.payload["side_effects"] is False
        assert rendered.payload["execution_contract_id"] == bundle.execution.contract_id
        assert rendered.payload["graph_id"] == bundle.graph.graph_id
        assert rendered.payload["kernel_activation"] == list(bundle.execution.kernel_activation)
        assert rendered.payload["constraints"] == list(bundle.intent.constraints)
        cores.append(
            (
                rendered.payload["source_bundle_digests"],
                rendered.payload["execution_contract_id"],
                rendered.payload["graph_id"],
                rendered.payload["canonical_json"],
            )
        )
    assert cores[0] == cores[1] == cores[2]


def test_render_stability(bundle) -> None:
    a = render_bundle(bundle, "generic_mcp", RENDERERS)
    b = render_bundle(bundle, "generic_mcp", RENDERERS)
    assert a.digest() == b.digest()


def test_unknown_target_fail_closed(bundle) -> None:
    with pytest.raises(InvalidValueError):
        render_bundle(bundle, "does_not_exist", RENDERERS)


def test_mcp_runtime_render_tool() -> None:
    server = build_server(ROOT)
    tool = server._tool_manager._tools["runtime_render"]  # noqa: SLF001
    out = tool.fn(mission="mcp render smoke", target="cursor")
    assert out["target"] == "cursor"
    assert "render_digest" in out
    assert out["payload"]["source_bundle_digests"]
