"""Package import smoke tests for the installable baseline."""

from __future__ import annotations

import importlib

from l9_cognitive_runtime import __version__


def test_package_import() -> None:
    module = importlib.import_module("l9_cognitive_runtime")
    assert module.__name__ == "l9_cognitive_runtime"
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"
