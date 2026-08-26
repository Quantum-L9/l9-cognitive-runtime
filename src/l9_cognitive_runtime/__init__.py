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
from l9_cognitive_runtime.service import (
    CognitiveRuntimeService,
    CompileObservationSession,
    CompileObserver,
    CompileRequest,
    ObserverErrorReporter,
    RuntimeBundle,
    RuntimeInvocationContext,
)

__all__ = [
    "__version__",
    "AdapterRender",
    "CognitiveRuntimeService",
    "CompileObservationSession",
    "CompileObserver",
    "CompileRequest",
    "ExecutionContract",
    "ExecutionGraph",
    "HandoffContract",
    "IntentContract",
    "ObserverErrorReporter",
    "RuntimeBundle",
    "RuntimeInvocationContext",
    "ValidationContract",
]

__version__ = "0.1.0"
