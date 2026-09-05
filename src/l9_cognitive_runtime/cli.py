"""CLI compatibility wrappers that preserve existing scripts and add in-memory compile.

The CLI is an outer host, so reading a governed ``ContextSnapshot`` from a file
happens here (INV-CTX-043) and never inside the semantic compiler, which does no
I/O at all (INV-CTX-033). The payload is validated into a typed snapshot before
compilation; a malformed payload fails closed rather than degrading to the empty
governed snapshot, which would silently mean something different.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from l9_cognitive_runtime.models.context import (
    SNAPSHOT_MAX_ITEMS,
    ContextSnapshot,
    payload_item_count,
)
from l9_cognitive_runtime.models.errors import InvalidValueError, ModelValidationError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def _confine(path: Path, root: Path, *, label: str) -> Path:
    """Resolve path against root and require the result to stay beneath it."""
    target = path.expanduser()
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InvalidValueError(
            f"{label} escapes allow_root",
            path=str(path),
            details={"allow_root": str(root), "resolved": str(target)},
        ) from exc
    return target


def _confined_write_dir(write_dir: Path, *, allow_root: Path | None = None) -> Path:
    """Resolve write_dir and require it to stay beneath allow_root (default: cwd)."""
    return _confine(write_dir, (allow_root or Path.cwd()).resolve(), label="write_dir")


def confined_output_path(output: Path | str, *, allow_root: Path | None = None) -> Path:
    """Resolve a CLI ``--out``/``--output`` argument beneath allow_root (default: cwd).

    A CLI output argument is untrusted input: an absolute path, a ``~`` prefix,
    or a ``..`` segment would otherwise let the caller write anywhere on the
    filesystem. The constructed path is validated here, before any write.
    """
    return _confine(Path(output), (allow_root or Path.cwd()).resolve(), label="output path")


def load_context_snapshot(path: Path) -> ContextSnapshot:
    """Read and validate a governed context snapshot from a JSON file."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise InvalidValueError("context snapshot file not found", path=str(resolved))
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidValueError(
            "context snapshot is not valid JSON", path=str(resolved), details=str(exc)
        ) from exc
    if not isinstance(payload, dict):
        raise InvalidValueError("context snapshot root must be an object", path=str(resolved))
    # Counted before typing: deriving a candidate's identity hashes it, so an
    # oversized payload must be refused before any of it is typed (INV-CTX-007).
    count = payload_item_count(payload)
    if count > SNAPSHOT_MAX_ITEMS:
        raise InvalidValueError(
            "context snapshot exceeds the maximum item count",
            path=str(resolved),
            details={"items": count, "max_items": SNAPSHOT_MAX_ITEMS},
        )
    try:
        return ContextSnapshot.from_mapping(payload)
    except ModelValidationError as exc:
        raise InvalidValueError(
            f"context snapshot is not a valid governed snapshot: {exc}",
            path=str(resolved),
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile cognitive runtime artifacts in memory")
    parser.add_argument("--mission", required=True)
    parser.add_argument("--task-type", default="kernel_runtime_convergence")
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument(
        "--context-snapshot",
        type=Path,
        default=None,
        help="Optional JSON file holding a governed ContextSnapshot",
    )
    parser.add_argument(
        "--plan-context",
        action="store_true",
        help="Emit the deterministic ContextPlan and stop before final compilation",
    )
    parser.add_argument(
        "--expected-context-plan-id",
        default=None,
        help="Fail closed if final compilation recomputes a different ContextPlan identity",
    )
    parser.add_argument(
        "--write-dir",
        type=Path,
        default=None,
        help="Optional directory under cwd for artifacts; omit for memory-only",
    )
    args = parser.parse_args(argv)
    if args.plan_context and args.expected_context_plan_id is not None:
        parser.error("--expected-context-plan-id cannot be used with --plan-context")

    snapshot = (
        load_context_snapshot(args.context_snapshot) if args.context_snapshot is not None else None
    )
    service = CognitiveRuntimeService()
    request = CompileRequest(
        mission=args.mission,
        task_type=args.task_type,
        pack_root=args.pack_root,
    )
    output_name = "bundle.json"
    if args.plan_context:
        plan = service.plan_context(request, discovery_snapshot=snapshot)
        payload = {
            "context_plan": plan.to_canonical_dict(),
            "context_plan_id": plan.context_plan_id,
            "context_plan_digest": plan.sha256(),
        }
        output_name = "context-plan.json"
    else:
        bundle = service.compile_runtime(
            request,
            context_snapshot=snapshot,
            expected_context_plan_id=args.expected_context_plan_id,
        )
        payload = {
            "digests": bundle.digests(),
            "context_plan": bundle.context_plan.to_canonical_dict(),
            "intent": bundle.intent.to_canonical_dict(),
            "compiled_task_context": bundle.task_context.to_canonical_dict(),
            "execution": bundle.execution.to_canonical_dict(),
            "validation": bundle.validation.to_canonical_dict(),
            "handoff": bundle.handoff.to_canonical_dict(),
            "graph": bundle.graph.to_canonical_dict(),
        }
    if args.write_dir is not None:
        out = _confined_write_dir(args.write_dir)
        out.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        destination = out / output_name
        destination.write_text(text, encoding="utf-8")
        print(destination)
    else:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
