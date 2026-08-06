"""MCP stdio server tests (no live transport)."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server, main

ROOT = Path(__file__).resolve().parents[1]


def test_five_read_only_tools_registered() -> None:
    server = build_server(ROOT)
    names = sorted(server._tool_manager._tools.keys())  # noqa: SLF001
    assert "compile_runtime" in names
    assert "get_run" in names
    assert set(READ_ONLY_TOOLS).issubset(set(names))


def test_compile_runtime_tool() -> None:
    server = build_server(ROOT)
    tool = server._tool_manager._tools["compile_runtime"]  # noqa: SLF001
    result = tool.fn(mission="mcp compile smoke")
    assert "digests" in result
    assert result["intent"]["mission"] == "mcp compile smoke"


def test_non_stdio_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("L9_MCP_TRANSPORT", "http")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
