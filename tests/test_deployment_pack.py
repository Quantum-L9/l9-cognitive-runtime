"""Deployment-pack tests for hosted MCP packaging."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from l9_cognitive_runtime.deployment import PACK_NAME, build_deployment_pack
from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=15))


def test_deployment_pack_verifies_compiles_and_preserves_resources(tmp_path: Path) -> None:
    pack_root = build_deployment_pack(
        ROOT,
        tmp_path / "pack",
        source_revision=REVISION,
    )
    pack = PackLoader().load(pack_root)
    assert pack.manifest["pack_name"] == PACK_NAME
    assert pack.manifest["source_revision"] == REVISION

    # PHASE-01 state: the deployment pack does not yet carry the live routing
    # sources (runtime/kernel_pipeline), so live compilation against it fails
    # closed. PHASE-08 (deployment semantic closure) converts this to a
    # successful dynamic compile from the sealed pack.
    with pytest.raises(InvalidValueError):
        CognitiveRuntimeService().compile_runtime(
            CompileRequest(mission="hosted MCP smoke", pack_root=pack_root)
        )

    server = build_server(pack_root)
    tools = _run(server.list_tools())
    assert {tool.name for tool in tools} == set(READ_ONLY_TOOLS)

    kernel_uri = f"l9://packs/{PACK_NAME}/kernels/repo_auditor_kernel.yaml"
    kernel = list(_run(server.read_resource(kernel_uri)))
    assert kernel[0].content.strip()

    schema_uri = f"l9://packs/{PACK_NAME}/schemas/execution_contract.schema.json"
    schema = list(_run(server.read_resource(schema_uri)))
    assert "properties" in schema[0].content


def test_deployment_pack_is_deterministic(tmp_path: Path) -> None:
    first = build_deployment_pack(ROOT, tmp_path / "first", source_revision=REVISION)
    second = build_deployment_pack(ROOT, tmp_path / "second", source_revision=REVISION)
    assert (first / "MANIFEST.json").read_bytes() == (second / "MANIFEST.json").read_bytes()


def test_deployment_pack_does_not_depend_on_repository_manifest(tmp_path: Path) -> None:
    pack_root = build_deployment_pack(ROOT, tmp_path / "pack", source_revision=REVISION)
    manifest = PackLoader().load(pack_root).manifest
    source_paths = {entry["source_path"] for entry in manifest["files"]}
    assert "MANIFEST.json" not in source_paths


def test_deployment_pack_rejects_non_commit_revision(tmp_path: Path) -> None:
    with pytest.raises(InvalidValueError):
        build_deployment_pack(ROOT, tmp_path / "pack", source_revision="main")
