"""CLI compatibility wrappers that preserve existing scripts and add in-memory compile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def _confined_write_dir(write_dir: Path, *, allow_root: Path | None = None) -> Path:
    """Resolve write_dir and require it to stay beneath allow_root (default: cwd)."""
    root = (allow_root or Path.cwd()).resolve()
    target = write_dir.expanduser().resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InvalidValueError(
            "write_dir escapes allow_root",
            path=str(write_dir),
            details={"allow_root": str(root), "resolved": str(target)},
        ) from exc
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile cognitive runtime artifacts in memory")
    parser.add_argument("--mission", required=True)
    parser.add_argument("--task-type", default="kernel_runtime_convergence")
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument(
        "--write-dir",
        type=Path,
        default=None,
        help="Optional directory under cwd for artifacts; omit for memory-only",
    )
    args = parser.parse_args(argv)

    service = CognitiveRuntimeService()
    bundle = service.compile_runtime(
        CompileRequest(
            mission=args.mission,
            task_type=args.task_type,
            pack_root=args.pack_root,
        )
    )
    payload = {
        "digests": bundle.digests(),
        "intent": bundle.intent.to_canonical_dict(),
        "execution": bundle.execution.to_canonical_dict(),
        "validation": bundle.validation.to_canonical_dict(),
        "handoff": bundle.handoff.to_canonical_dict(),
        "graph": bundle.graph.to_canonical_dict(),
    }
    if args.write_dir is not None:
        out = _confined_write_dir(args.write_dir)
        out.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        (out / "bundle.json").write_text(text, encoding="utf-8")
        print(out / "bundle.json")
    else:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
