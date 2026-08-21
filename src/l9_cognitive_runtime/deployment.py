"""Build a minimal, manifest-verified pack for hosted MCP deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

import yaml

from l9_cognitive_runtime.models.errors import InvalidValueError

PACK_NAME = "l9-cognitive-runtime-deployment"
SOURCE_REPOSITORY = "https://github.com/Quantum-L9/l9-cognitive-runtime"
_REQUIRED_CONTRACTS = (
    "FINAL_EXECUTION_CONTRACT.yaml",
    "VALIDATION_CONTRACT.yaml",
    "HANDOFF_CONTRACT.yaml",
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _source_file(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise InvalidValueError("deployment source path escapes repository", path=relative)
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise InvalidValueError("deployment source path escapes repository", path=relative) from exc
    if not candidate.is_file():
        raise InvalidValueError("deployment source file missing", path=relative)
    return candidate


def build_deployment_pack(
    source_root: Path,
    destination: Path,
    *,
    source_revision: str,
) -> Path:
    """Seal the canonical contracts and activated kernels into a verified pack.

    The mutable repository-root MANIFEST.json is deliberately not consumed. The
    deployment pack receives its own manifest over exactly the files copied into
    the image, with every entry linked back to its canonical repository path.
    """
    source = source_root.resolve()
    dest = destination.resolve()
    revision = source_revision.strip().lower()
    if not _FULL_SHA.fullmatch(revision):
        raise InvalidValueError("source_revision must be a full 40-character git SHA")
    if not source.is_dir():
        raise InvalidValueError("source_root must be a directory", path=str(source))
    if dest == source or source in dest.parents:
        raise InvalidValueError("destination must be outside source_root", path=str(dest))
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise InvalidValueError("destination must be absent or empty", path=str(dest))
    dest.mkdir(parents=True, exist_ok=True)

    execution_path = _source_file(source, "FINAL_EXECUTION_CONTRACT.yaml")
    raw: Any = yaml.safe_load(execution_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise InvalidValueError("execution contract root must be a mapping")
    execution = cast("dict[str, Any]", raw)
    activation = execution.get("kernel_activation")
    if not isinstance(activation, list) or not activation:
        raise InvalidValueError("execution contract requires kernel_activation")
    kernels = [item for item in activation if isinstance(item, str) and item.strip()]
    if len(kernels) != len(activation):
        raise InvalidValueError("kernel_activation entries must be non-empty strings")

    copies: dict[str, str] = {}

    def register(source_rel: str, dest_rel: str | None = None) -> None:
        src = _source_file(source, source_rel)
        target_rel = (dest_rel or source_rel).replace("\\", "/")
        existing = copies.get(target_rel)
        if existing is not None and existing != source_rel:
            raise InvalidValueError(
                "deployment alias collision",
                path=target_rel,
                details={"first": existing, "second": source_rel},
            )
        copies[target_rel] = source_rel
        # Resolve now so a bad registration fails before any bytes are written.
        src.relative_to(source)

    for relative in _REQUIRED_CONTRACTS:
        register(relative)

    source_plan = execution.get("source_activation_plan")
    if isinstance(source_plan, str) and source_plan.strip():
        register(source_plan.strip())

    for kernel in kernels:
        relative = kernel.strip().replace("\\", "/")
        register(relative)
        # Preserve the public MCP resource URI shape: l9://.../kernels/<filename>.
        register(relative, f"kernels/{Path(relative).name}")

    schema_root = source / "contracts"
    schemas = sorted(schema_root.glob("*.schema.json")) if schema_root.is_dir() else []
    if not schemas:
        raise InvalidValueError("no contract schemas found", path="contracts")
    for schema in schemas:
        relative = schema.relative_to(source).as_posix()
        register(relative)
        # Preserve the public MCP resource URI shape: l9://.../schemas/<filename>.
        register(relative, f"schemas/{schema.name}")

    entries: list[dict[str, Any]] = []
    for target_rel in sorted(copies):
        source_rel = copies[target_rel]
        data = _source_file(source, source_rel).read_bytes()
        target = dest / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entries.append(
            {
                "path": target_rel,
                "source_path": source_rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest = {
        "manifest_format": "l9.mcp.deployment-pack.v1",
        "pack_name": PACK_NAME,
        "pack_version": revision[:12],
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": revision,
        "files": entries,
    }
    (dest / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the hosted MCP deployment pack")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    build_deployment_pack(
        args.source_root,
        args.destination,
        source_revision=args.source_revision,
    )


if __name__ == "__main__":
    main()
