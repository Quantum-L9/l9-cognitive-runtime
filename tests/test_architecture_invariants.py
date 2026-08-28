"""Static architecture drift guards (A041-A044, A057, INV-CTX-039).

These are repository-shape checks, deliberately *not* per-compile runtime
checks: forbidding an import or a module is a property of the tree, and paying
for it on every compile would be the wrong trade (INV-CTX-039).

They exist because the failure they catch is silent. Nothing at runtime tells
you that the semantic compiler grew an HTTP client, that a second compiler
appeared beside the live one, or that requirement planning started reading
obligations. Each of those would still compile, still pass, and still be wrong.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "l9_cognitive_runtime"
SEMANTIC_COMPILER = PACKAGE / "compiler"

# Anything that would let the semantic compiler acquire context or cause an
# effect (INV-CTX-033, INV-CTX-034, INV-CTX-035).
FORBIDDEN_IMPORTS = frozenset(
    {
        "l9_observability_core",
        "opentelemetry",
        "requests",
        "httpx",
        "httpx2",
        "boto3",
        "redis",
        "neo4j",
        "graphiti_core",
        "subprocess",
        "socket",
        "urllib",
        "sqlite3",
    }
)

FORBIDDEN_MODULES = (
    "observability.py",
    "telemetry.py",
    "tracing.py",
    "memory_store.py",
    "world_state.py",
)

# Requirement planning precedes obligation derivation and may never consult it
# or any downstream execution IR (A057).
REQUIREMENT_PLANNING_FORBIDDEN_DEPS = (
    "l9_cognitive_runtime.compiler.obligations",
    "l9_cognitive_runtime.compiler.execution",
    "l9_cognitive_runtime.compiler.validation",
    "l9_cognitive_runtime.compiler.handoff",
    "l9_cognitive_runtime.compiler.packet",
    "l9_cognitive_runtime.compiler.pipeline",
    "l9_cognitive_runtime.graph",
)


def semantic_compiler_sources() -> list[Path]:
    return sorted(SEMANTIC_COMPILER.rglob("*.py"))


def imported_roots(path: Path) -> set[str]:
    """Every top-level module name this file imports, at any statement depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


# --------------------------------------------------------------------------
# A041 / A042 / A043: no acquisition, no observability, no world state.
# --------------------------------------------------------------------------


def test_the_semantic_compiler_imports_no_acquisition_or_effect_client() -> None:
    offenders: dict[str, set[str]] = {}
    for path in semantic_compiler_sources():
        forbidden = imported_roots(path) & FORBIDDEN_IMPORTS
        if forbidden:
            offenders[path.relative_to(ROOT).as_posix()] = forbidden
    assert offenders == {}


def test_no_forbidden_module_exists_anywhere_in_the_package() -> None:
    present = [
        path.relative_to(ROOT).as_posix()
        for name in FORBIDDEN_MODULES
        for path in PACKAGE.rglob(name)
    ]
    assert present == []


def test_no_trace_or_span_ownership_leaked_into_the_compiler() -> None:
    # Word-boundary matching: "span" must not match "spanning", and the
    # compiler legitimately discusses "tracing" nothing at all.
    pattern = re.compile(r"\b(TraceContext|SpanContext|start_span|tracer|Exporter)\b")
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in semantic_compiler_sources()
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# --------------------------------------------------------------------------
# A040: legitimate manifest-bound local pack reads survive.
# --------------------------------------------------------------------------


def test_manifest_bound_pack_reads_remain_available_to_the_compiler() -> None:
    """``pathlib`` is permitted; the pack is an immutable verified input."""
    users = {path.name for path in semantic_compiler_sources() if "pathlib" in imported_roots(path)}
    # These are the modules that resolve routing rules, the pipeline
    # definition, kernels, and adapter templates from the verified pack.
    assert {"pipeline.py", "kernels.py", "activation.py", "adapters.py"} <= users


# --------------------------------------------------------------------------
# A057: requirement planning does not depend on downstream obligations.
# --------------------------------------------------------------------------


def test_requirement_planning_has_no_downstream_dependency() -> None:
    planner = SEMANTIC_COMPILER / "context_requirements.py"
    modules = imported_modules(planner)
    assert not (modules & set(REQUIREMENT_PLANNING_FORBIDDEN_DEPS))


def test_context_compilation_has_no_downstream_dependency() -> None:
    for name in ("task_scope.py", "task_context.py"):
        modules = imported_modules(SEMANTIC_COMPILER / name)
        # ``execution`` is excluded here too: the compiler receives the default
        # authority order as a parameter rather than importing the contract
        # compiler, so context compilation stays upstream of execution.
        assert not (modules & set(REQUIREMENT_PLANNING_FORBIDDEN_DEPS)), name


# --------------------------------------------------------------------------
# INV-CTX-002: exactly one live semantic spine.
# --------------------------------------------------------------------------


def test_exactly_one_compile_pipeline_class_exists() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in PACKAGE.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        if isinstance(node, ast.ClassDef) and node.name == "CompilePipeline"
    ]
    assert definitions == ["src/l9_cognitive_runtime/compiler/pipeline.py"]


def test_the_service_delegates_to_that_one_pipeline() -> None:
    service = (PACKAGE / "service.py").read_text(encoding="utf-8")
    assert "CompilePipeline().compile(" in service
    # No second composition root: the service never assembles IRs itself.
    for owner in ("ObjectiveDeriver", "ActivationPlanner", "ContextCompiler"):
        assert owner not in service


def test_context_stages_are_owned_by_the_pipeline_not_duplicated() -> None:
    pipeline = (SEMANTIC_COMPILER / "pipeline.py").read_text(encoding="utf-8")
    for stage in (
        "TaskScopeCompiler()",
        "ContextDiscoveryCompiler()",
        "ContextRequirementPlanner()",
        "ContextCompiler()",
        "ContextClosureValidator()",
    ):
        assert pipeline.count(stage) == 1, stage


# --------------------------------------------------------------------------
# A001: the architecture law is present at the repository root.
# --------------------------------------------------------------------------


def test_repository_root_invariants_document_is_present_and_complete() -> None:
    invariants = ROOT / "INVARIANTS.md"
    assert invariants.is_file()
    text = invariants.read_text(encoding="utf-8")
    declared = {f"INV-CTX-{index:03d}" for index in range(1, 43)}
    missing = sorted(name for name in declared if f"### {name}:" not in text)
    assert missing == []


def test_the_compiled_context_schema_ships_with_the_contracts() -> None:
    assert (ROOT / "contracts" / "compiled_task_context.schema.json").is_file()


# --------------------------------------------------------------------------
# A044: no new runtime dependency was introduced.
# --------------------------------------------------------------------------


def test_no_new_runtime_dependency_was_added() -> None:
    tomllib = pytest.importorskip("tomllib")
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {
        re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        for spec in manifest["project"]["dependencies"]
    }
    assert runtime == {"mcp", "pydantic", "pyyaml"}
