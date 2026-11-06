# >>> l9:meta >>>
# id: l9-cognitive-runtime.test.tests_test_package_import__py
# title: test package import
# artifact_type: test
# mcp_primitive: none
# callable: false
# retrievable: false
# injectable: false
# namespace: l9-cognitive-runtime
# sharing_scope: agnostic
# source_path: tests/test_package_import.py
# content_hash: ddce410953c6a3c3bfa3e908ece66f6ca5fefcefc13b2d2b6fa6b62427083ff3
# token_cost_estimate: 97
# authority: Quantum-L9
# created_or_detected_at: Unknown
# owner: Unknown
# <<< l9:meta <<<
"""Package import smoke tests for the installable baseline."""

from __future__ import annotations

import importlib

from l9_cognitive_runtime import __version__


def test_package_import() -> None:
    module = importlib.import_module("l9_cognitive_runtime")
    assert module.__name__ == "l9_cognitive_runtime"
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"
