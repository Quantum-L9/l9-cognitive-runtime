"""Deterministic render-only agent adapters (L9CR-MCP-016)."""

from __future__ import annotations

from l9_cognitive_runtime.adapters.base import RenderedAdapter, Renderer, render_bundle
from l9_cognitive_runtime.adapters.claude_code import ClaudeCodeRenderer
from l9_cognitive_runtime.adapters.cursor import CursorRenderer
from l9_cognitive_runtime.adapters.generic_mcp import GenericMcpRenderer

RENDERERS: dict[str, Renderer] = {
    "generic_mcp": GenericMcpRenderer(),
    "claude_code": ClaudeCodeRenderer(),
    "cursor": CursorRenderer(),
}

__all__ = [
    "RENDERERS",
    "RenderedAdapter",
    "ClaudeCodeRenderer",
    "CursorRenderer",
    "GenericMcpRenderer",
    "Renderer",
    "render_bundle",
]
