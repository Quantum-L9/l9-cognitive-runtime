"""End-to-end tests for the read-only stdio MCP server (L9CR-MCP-008B)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import anyio
import pytest

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server, main


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=15))


def _tool_data(result: Any) -> dict[str, Any]:
    assert result.is_error is False, getattr(result, "content", result)
    if getattr(result, "structured_content", None):
        return cast("dict[str, Any]", result.structured_content)
    return cast("dict[str, Any]", json.loads(result.content[0].text))


# --- transport / pack-root guards -------------------------------------------


def test_main_rejects_non_stdio_transport(
    valid_pack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("L9_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("L9_PACK_ROOT", str(valid_pack))
    with pytest.raises(SystemExit):
        main()


def test_main_requires_pack_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("L9_MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("L9_PACK_ROOT", raising=False)
    with pytest.raises(SystemExit):
        main()


# --- tool surface ------------------------------------------------------------


def test_tools_are_exactly_the_read_only_surface(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    tools = _run(server.list_tools())
    assert {t.name for t in tools} == set(READ_ONLY_TOOLS)


def test_no_mutating_or_shell_tool_registered(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    names = {t.name for t in _run(server.list_tools())}
    forbidden = {"run", "exec", "shell", "write", "delete", "mutate", "apply"}
    assert not (names & forbidden)
    assert all(not any(f in n for f in ("shell", "exec", "write")) for n in names)


def test_compile_runtime_tool_success(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    result = _run(server.call_tool("compile_runtime", {"mission": "e2e compile"}))
    data = _tool_data(result)
    assert data["execution_contract_id"] == "FINAL_EXECUTION_CONTRACT"
    assert data["digests"]["graph"]
    assert data["provenance"]["manifest_digest"]


def test_compile_runtime_invalid_input(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    # In-process dispatch surfaces a tool error as a raised ToolError.
    with pytest.raises(Exception):  # noqa: B017
        _run(server.call_tool("compile_runtime", {"mission": ""}))


def test_capabilities_declare_read_only(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    data = _tool_data(_run(server.call_tool("runtime_capabilities", {})))
    assert data["writes"] is False
    assert data["execution"] is False
    assert data["shell"] is False


# --- resources ---------------------------------------------------------------


def test_resource_version_read(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    contents = list(_run(server.read_resource("l9://runtime/version")))
    assert contents[0].content.strip()


def test_resource_kernel_read(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    contents = list(_run(server.read_resource("l9://packs/test-pack/kernels/repo_auditor.yaml")))
    assert "kernel_id" in contents[0].content


def test_unknown_pack_ref_rejected(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    with pytest.raises(Exception):  # noqa: B017 - SDK wraps as an MCP error
        list(_run(server.read_resource("l9://packs/not-the-bound-pack/manifest")))


def test_missing_kernel_resource_rejected(valid_pack: Path) -> None:
    server = build_server(valid_pack)
    with pytest.raises(Exception):  # noqa: B017
        list(_run(server.read_resource("l9://packs/test-pack/kernels/ghost.yaml")))


# --- wire-level: initialize handshake + clean shutdown -----------------------


def test_wire_initialize_list_and_call(valid_pack: Path) -> None:
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    async def scenario() -> None:
        server = build_server(valid_pack)
        low = server._lowlevel_server
        init_options = low.create_initialization_options()
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            client_read, client_write = client_streams
            server_read, server_write = server_streams
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    lambda: low.run(server_read, server_write, init_options, raise_exceptions=True)
                )
                async with ClientSession(client_read, client_write) as session:
                    init_result = await session.initialize()
                    assert init_result.server_info.name == "l9-cognitive-runtime"
                    tools = await session.list_tools()
                    assert {t.name for t in tools.tools} == set(READ_ONLY_TOOLS)
                    called = await session.call_tool("runtime_capabilities", {})
                    assert called.is_error is False
                # Client session closed cleanly; stop the server task.
                tg.cancel_scope.cancel()

    _run(scenario())
