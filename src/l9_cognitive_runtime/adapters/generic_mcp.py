"""Generic MCP adapter renderer."""

from __future__ import annotations

from l9_cognitive_runtime.adapters.base import RenderedAdapter, render_document
from l9_cognitive_runtime.service import RuntimeBundle


class GenericMcpRenderer:
    target = "generic_mcp"

    def render(self, bundle: RuntimeBundle) -> RenderedAdapter:
        return RenderedAdapter(
            target=self.target,
            payload=render_document("mcp", bundle, adapter=self.target),
        )
