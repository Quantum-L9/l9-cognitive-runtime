"""L9 Cognitive Runtime — installable package baseline.

This package intentionally does not relocate the existing ``runtime/`` kernel
pack. Cognitive-runtime semantics remain in the repository tree; later
contracts migrate typed surfaces under this namespace.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
