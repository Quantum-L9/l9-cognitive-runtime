# >>> l9:meta >>>
# id: l9-cognitive-runtime.source.src_l9_cognitive_runtime_init__py
# title: init
# artifact_type: source
# mcp_primitive: resource
# callable: false
# retrievable: true
# injectable: true
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: src/l9_cognitive_runtime/__init__.py
# content_hash: ee697ba174842b4936b2dc2bf86a95b9307b2ea30be243f0ecab9aacb8a07ed1
# token_cost_estimate: 230
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""L9 Cognitive Runtime — installable package baseline.

This package intentionally does not relocate the existing ``runtime/`` kernel
pack. Cognitive-runtime semantics remain in the repository tree; later
contracts migrate typed surfaces under this namespace.
"""

from __future__ import annotations

from l9_cognitive_runtime.models import (
    AdapterRender,
    ContextPlan,
    ContextSnapshot,
    ExecutionContract,
    ExecutionGraph,
    HandoffContract,
    IntentContract,
    ValidationContract,
)
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest, RuntimeBundle

__all__ = [
    "__version__",
    "AdapterRender",
    "CognitiveRuntimeService",
    "CompileRequest",
    "ContextPlan",
    "ContextSnapshot",
    "ExecutionContract",
    "ExecutionGraph",
    "HandoffContract",
    "IntentContract",
    "RuntimeBundle",
    "ValidationContract",
]

__version__ = "0.1.0"
