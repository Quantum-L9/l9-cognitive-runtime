"""CLI compatibility wrappers that preserve existing scripts and add in-memory compile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile cognitive runtime artifacts in memory")
    parser.add_argument("--mission", required=True)
    parser.add_argument("--task-type", default="kernel_runtime_convergence")
    parser.add_argument("--pack-root", type=Path, default=None)
    parser.add_argument(
        "--write-dir",
        type=Path,
        default=None,
        help="Optional directory to materialize artifacts; omitted keeps results in memory only",
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
        out = args.write_dir
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
