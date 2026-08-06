"""Cursor adapter renderer (serialize-only)."""

from __future__ import annotations

from l9_cognitive_runtime.adapters.base import RenderedAdapter, render_document
from l9_cognitive_runtime.service import RuntimeBundle


class CursorRenderer:
    target = "cursor"

    def render(self, bundle: RuntimeBundle) -> RenderedAdapter:
        doc = render_document("cursor", bundle, adapter=self.target)
        doc["client_hints"] = {"config": ".cursor/mcp.json", "transport": "http_or_stdio"}
        return RenderedAdapter(target=self.target, payload=doc)
