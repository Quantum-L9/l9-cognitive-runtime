"""Renderer interface — serialize only; never plan or mutate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from l9_cognitive_runtime.models.canonical import canonical_json, sha256_digest
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import RuntimeBundle


@dataclass(frozen=True)
class RenderedAdapter:
    target: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target, "payload": self.payload}

    def digest(self) -> str:
        return sha256_digest(self.to_dict())


class Renderer(Protocol):
    target: str

    def render(self, bundle: RuntimeBundle) -> RenderedAdapter: ...


def semantic_core(bundle: RuntimeBundle) -> dict[str, Any]:
    """Authority-preserving fields shared across adapters."""
    return {
        "source_bundle_digests": bundle.digests(),
        "execution_contract_id": bundle.execution.contract_id,
        "graph_id": bundle.graph.graph_id,
        "terminal_node": bundle.graph.terminal_node,
        "nodes": [node.to_canonical_dict() for node in bundle.graph.nodes],
        "edges": [edge.to_canonical_dict() for edge in bundle.graph.edges],
        "kernel_activation": list(bundle.execution.kernel_activation),
        "constraints": list(bundle.intent.constraints),
        "unknowns": list(bundle.intent.unknowns or ()),
        "authority": {
            "task_type": bundle.intent.task_type,
            "mission": bundle.intent.mission,
            "handoff_contract_id": bundle.handoff.contract_id,
            "validation_contract_id": bundle.validation.contract_id,
            "authority_order": list(bundle.execution.authority_order),
        },
        "side_effects": False,
        "planning": False,
        "execution": False,
    }


def render_document(target: str, bundle: RuntimeBundle, *, adapter: str) -> dict[str, Any]:
    core = semantic_core(bundle)
    return {
        "adapter": adapter,
        "target": target,
        "format": "l9.adapter-render/1",
        **core,
        "canonical_json": canonical_json(core),
    }


def render_bundle(
    bundle: RuntimeBundle,
    target: str,
    renderers: dict[str, Renderer],
) -> RenderedAdapter:
    renderer = renderers.get(target)
    if renderer is None:
        raise InvalidValueError("unknown adapter target", path="target", details={"target": target})
    rendered = renderer.render(bundle)
    if rendered.payload.get("source_bundle_digests") != bundle.digests():
        raise InvalidValueError("render lost source bundle digests", path="source_bundle_digests")
    if rendered.payload.get("planning") or rendered.payload.get("execution"):
        raise InvalidValueError("render must not enable planning/execution", path="side_effects")
    return rendered
