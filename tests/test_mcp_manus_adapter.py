"""Tests for the bounded, locally-connected Manus Cog adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import anyio
import pytest

from l9_cognitive_runtime.mcp.manus_adapter import (
    MANUS_READ_ONLY_TOOLS,
    MANUS_SERVER_NAME,
    build_server,
    main,
)
from l9_cognitive_runtime.models.errors import InvalidValueError


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=15))


def _tool_data(result: Any) -> dict[str, Any]:
    assert result.is_error is False, getattr(result, "content", result)
    if getattr(result, "structured_content", None):
        return cast("dict[str, Any]", result.structured_content)
    return cast("dict[str, Any]", json.loads(result.content[0].text))


def test_tools_are_exactly_the_bounded_cog_namespace(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    assert {tool.name for tool in _run(server.list_tools())} == set(MANUS_READ_ONLY_TOOLS)


def test_capabilities_identify_the_adapter_and_read_only_boundary(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    data = _tool_data(_run(server.call_tool("cog_runtime_capabilities", {})))
    assert data["server"] == MANUS_SERVER_NAME
    assert data["tools"] == list(MANUS_READ_ONLY_TOOLS)
    assert data["writes"] is False
    assert data["execution"] is False
    assert data["shell"] is False


def test_compile_runtime_uses_the_verified_bound_pack(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    data = _tool_data(_run(server.call_tool("cog_compile_runtime", {"mission": "adapter test"})))
    assert data["execution_contract_id"] == "FINAL_EXECUTION_CONTRACT"
    assert data["provenance"]["manifest_digest"]
    assert data["run_id"]


def test_adapter_refuses_a_tampered_pack(valid_pack: Path) -> None:
    target = valid_pack / "kernels" / "repo_auditor.yaml"
    target.write_text("kernel_id: tampered\n", encoding="utf-8")
    with pytest.raises(InvalidValueError, match="hash mismatch"):
        build_server(valid_pack)


def test_main_refuses_non_stdio_transport(
    valid_pack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("L9_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("L9_PACK_ROOT", str(valid_pack))
    with pytest.raises(SystemExit):
        main()


def test_main_requires_an_explicit_pack_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("L9_MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("L9_PACK_ROOT", raising=False)
    with pytest.raises(SystemExit):
        main()


def test_wire_initialize_lists_and_calls_only_the_adapter_surface(valid_pack: Path) -> None:
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    async def scenario() -> None:
        server = build_server(valid_pack)
        low = server._lowlevel_server
        init_options = low.create_initialization_options()
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            client_read, client_write = client_streams
            server_read, server_write = server_streams
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(
                    lambda: low.run(server_read, server_write, init_options, raise_exceptions=True)
                )
                async with ClientSession(client_read, client_write) as session:
                    initialized = await session.initialize()
                    assert initialized.server_info.name == MANUS_SERVER_NAME
                    tools = await session.list_tools()
                    assert {tool.name for tool in tools.tools} == set(MANUS_READ_ONLY_TOOLS)
                    called = await session.call_tool(
                        "cog_validate_runtime_bundle", {"mission": "wire test"}
                    )
                    assert called.is_error is False
                task_group.cancel_scope.cancel()

    _run(scenario())
