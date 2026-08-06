"""L9 Cognitive Runtime — installable package baseline.

This package intentionally does not relocate the existing ``runtime/`` kernel
pack. Cognitive-runtime semantics remain in the repository tree; later
contracts migrate typed surfaces under this namespace.
"""

from __future__ import annotations

from l9_cognitive_runtime.models import (
    AdapterRender,
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
    "ExecutionContract",
    "ExecutionGraph",
    "HandoffContract",
    "IntentContract",
    "RuntimeBundle",
    "ValidationContract",
]

__version__ = "0.1.0"
