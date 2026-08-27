"""Build a semantically closed, manifest-verified pack for hosted MCP
deployment (PHASE-08, INV-011).

The sealed pack contains everything required to dynamically compile every
supported mission route without a repository checkout: routing rules, the
pipeline definition, the kernel role registry, every dynamically selectable
kernel, objective derivation inputs, compiler-required contracts, schemas,
convergence definition, validation semantics, and a provenance manifest.

Selection never originates from the static FINAL_EXECUTION_CONTRACT.yaml
(A0801): the static contracts are copied only as museum examples. Before
sealing, a closure validator proves every supported route compiles against
the pack itself (A0802).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from l9_cognitive_runtime.models.errors import InvalidValueError

PACK_NAME = "l9-cognitive-runtime-deployment"
SOURCE_REPOSITORY = "https://github.com/Quantum-L9/l9-cognitive-runtime"
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

# Museum examples: inert, never selection authority (INV-009).
_MUSEUM_CONTRACTS = (
    "FINAL_EXECUTION_CONTRACT.yaml",
    "VALIDATION_CONTRACT.yaml",
    "HANDOFF_CONTRACT.yaml",
    "EXECUTION_GRAPH.json",
)

# Compiler-required semantic sources (INV-011 closure set).
_CLOSURE_SOURCES = (
    "runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml",
    "runtime/kernel_pipeline/KERNEL_PIPELINE.yaml",
    "runtime/kernel_pipeline/KERNEL_ROLE_MAP.yaml",
    "runtime/kernel_pipeline/planner/ACTIVATION_PLAN_SCHEMA.yaml",
    "runtime/intent_compiler/INTENT_COMPILER.yaml",
    "runtime/execution_graph/graph.schema.json",
    "runtime/kernels/terminal/flawless_victory.contract.yaml",
)


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


def _iter_kernel_sources(root: Path) -> list[str]:
    kernels_root = root / "runtime" / "kernels"
    if not kernels_root.is_dir():
        raise InvalidValueError("runtime/kernels missing", path="runtime/kernels")
    return sorted(
        path.relative_to(root).as_posix()
        for path in kernels_root.rglob("*")
        if path.is_file()
    )


def _iter_schema_sources(root: Path) -> list[str]:
    schema_root = root / "contracts"
    if not schema_root.is_dir():
        raise InvalidValueError("contracts missing", path="contracts")
    return sorted(
        path.relative_to(root).as_posix()
        for path in schema_root.glob("*.schema.json")
        if path.is_file()
    )


def _iter_adapter_sources(root: Path) -> list[str]:
    adapter_root = root / "runtime" / "contract_compiler" / "adapters"
    if not adapter_root.is_dir():
        raise InvalidValueError("adapter templates missing", path=str(adapter_root))
    return sorted(
        path.relative_to(root).as_posix()
        for path in adapter_root.glob("*.md")
        if path.is_file()
    )


def validate_deployment_closure(pack_root: Path) -> dict[str, Any]:
    """A0802: prove every supported route compiles from the sealed pack."""
    from l9_cognitive_runtime.compiler.activation import ActivationPlanner
    from l9_cognitive_runtime.compiler.objective import ObjectiveDeriver
    from l9_cognitive_runtime.pack import PackLoader
    from l9_cognitive_runtime.parsing import load_yaml_file
    from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

    pack = PackLoader().load(pack_root)
    rules = load_yaml_file(pack.resolve("runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml"))
    routes = rules.get("task_routes") or {}
    service = CognitiveRuntimeService()
    deriver = ObjectiveDeriver()
    planner = ActivationPlanner()
    compiled_routes: list[str] = []
    for route_name, route in sorted(routes.items()):
        tokens = route.get("match_any") or []
        if not tokens:
            raise InvalidValueError("route without match_any tokens", path=route_name)
        mission = f"Representative {tokens[0]} mission"
        intent = deriver.derive(CompileRequest(mission=mission))
        plan = planner.plan(
            intent,
            rules_path=pack.resolve("runtime/kernel_pipeline/planner/TASK_ROUTING_RULES.yaml"),
            pipeline_path=pack.resolve("runtime/kernel_pipeline/KERNEL_PIPELINE.yaml"),
        )
        if plan.blockers:
            raise InvalidValueError(
                "route activation blocked in sealed pack",
                path=route_name,
                details={"blockers": plan.blockers},
            )
        # Full spine compile against the sealed pack: kernel resolution,
        # obligations, liveness, graph, packet — all fail closed.
        service.compile_runtime(CompileRequest(mission=mission, pack_root=pack_root))
        compiled_routes.append(route_name)
    return {"routes_compiled": compiled_routes, "count": len(compiled_routes)}


def build_deployment_pack(
    source_root: Path,
    destination: Path,
    *,
    source_revision: str,
) -> Path:
    """Seal the semantic closure set into a verified pack and prove closure."""
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
        src.relative_to(source)

    # Museum contracts: inert examples, never selection authority (A0801).
    for relative in _MUSEUM_CONTRACTS:
        register(relative)
    # Compiler-required semantic sources.
    for relative in _CLOSURE_SOURCES:
        register(relative)
    # Every dynamically selectable kernel (A0801: no static preselection).
    for relative in _iter_kernel_sources(source):
        register(relative)
        # Preserve the public MCP resource URI shape: l9://.../kernels/<name>.
        register(relative, f"kernels/{Path(relative).name}")
    # Schemas, adapter templates, and the validation report convention.
    for relative in _iter_schema_sources(source):
        register(relative)
        register(relative, f"schemas/{Path(relative).name}")
    for relative in _iter_adapter_sources(source):
        register(relative)

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

    # A0802: prove every supported route compiles from the sealed pack
    # before the manifest is finalized — an unproven pack cannot be sealed.
    base_manifest: dict[str, Any] = {
        "manifest_format": "l9.mcp.deployment-pack.v1",
        "pack_name": PACK_NAME,
        "pack_version": revision[:12],
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": revision,
        "files": entries,
    }
    (dest / "MANIFEST.json").write_text(
        json.dumps(base_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    closure = validate_deployment_closure(dest)
    base_manifest["semantic_closure"] = closure
    (dest / "MANIFEST.json").write_text(
        json.dumps(base_manifest, indent=2, sort_keys=True) + "\n",
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
