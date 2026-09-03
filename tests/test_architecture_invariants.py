"""Static architecture drift guards (INV-CTX-002, 033, 034, 035, 039, 041).

These are repository-shape checks, deliberately *not* per-compile runtime
checks: forbidding an import or a second composition owner is a property of the
tree, and paying for it on every compile would be the wrong trade.

They exist because the failure they catch is silent. Nothing at runtime tells
you that the semantic compiler grew an HTTP client, that a second compiler
appeared beside the live one, that requirement planning started reading
obligations, or that a liveness check quietly became a constant. Each of those
would still compile, still pass, and still be wrong.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "l9_cognitive_runtime"
SEMANTIC_COMPILER = PACKAGE / "compiler"
LEGACY_RUNTIME = ROOT / "runtime"

# Anything that would let the semantic compiler acquire context or cause an
# effect (INV-CTX-033, INV-CTX-034, INV-CTX-035).
FORBIDDEN_IMPORTS = frozenset(
    {
        "l9_observability_core",
        "opentelemetry",
        "requests",
        "httpx",
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

# Requirement planning and context compilation precede obligation derivation and
# may never consult it or any downstream execution IR.
UPSTREAM_FORBIDDEN_DEPS = (
    "l9_cognitive_runtime.compiler.obligations",
    "l9_cognitive_runtime.compiler.execution",
    "l9_cognitive_runtime.compiler.validation",
    "l9_cognitive_runtime.compiler.handoff",
    "l9_cognitive_runtime.compiler.packet",
    "l9_cognitive_runtime.compiler.pipeline",
    "l9_cognitive_runtime.compiler.liveness",
    "l9_cognitive_runtime.graph",
)

# The semantic stage owners. Sequencing them is what makes something a
# composition root, and exactly one module may do it (INV-CTX-002).
STAGE_OWNERS = frozenset(
    {
        "ObjectiveDeriver",
        "TaskScopeCompiler",
        "ContextDiscoveryCompiler",
        "ActivationPlanner",
        "KernelResolver",
        "ContextRequirementPlanner",
        "ContextCompiler",
        "ContextClosureValidator",
        "ObligationDeriver",
        "ExecutionContractCompiler",
        "ValidationContractCompiler",
        "HandoffContractCompiler",
    }
)

THE_ONE_COMPOSITION_OWNER = "src/l9_cognitive_runtime/compiler/pipeline.py"


def python_sources(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_roots(path: Path) -> set[str]:
    """Every top-level module name this file imports, at any statement depth."""
    roots: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def instantiated_stage_owners(path: Path) -> set[str]:
    """Stage-owner classes this file actually constructs."""
    found: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in STAGE_OWNERS:
                found.add(node.func.id)
    return found


def attribute_references(path: Path, name: str) -> list[int]:
    """Line numbers where this file names ``.<name>`` on any object.

    Matched on the attribute rather than the receiver's type, because a
    resolution passed in as a parameter has no visible type at the call site —
    and it is precisely the parameter case that would slip past a guard keyed
    on a local variable's name.
    """
    return sorted(
        node.lineno
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Attribute) and node.attr == name
    )


# --------------------------------------------------------------------------
# INV-CTX-033/034/035: no acquisition, no observability, no world state.
# --------------------------------------------------------------------------


def test_the_semantic_compiler_imports_no_acquisition_or_effect_client() -> None:
    offenders: dict[str, set[str]] = {}
    for path in python_sources(SEMANTIC_COMPILER):
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
    # Word-boundary matching: "span" must not match "spanning".
    pattern = re.compile(r"\b(TraceContext|SpanContext|start_span|tracer|Exporter)\b")
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in python_sources(SEMANTIC_COMPILER)
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_manifest_bound_pack_reads_remain_available_to_the_compiler() -> None:
    """``pathlib`` is permitted; the pack is an immutable verified input."""
    users = {
        path.name for path in python_sources(SEMANTIC_COMPILER) if "pathlib" in imported_roots(path)
    }
    assert {"pipeline.py", "kernels.py", "activation.py", "adapters.py"} <= users


def test_the_context_projections_perform_no_file_io() -> None:
    """Discovery and selection project an injected snapshot; they never read."""
    for name in ("task_scope.py", "task_context.py", "context_requirements.py"):
        source = (SEMANTIC_COMPILER / name).read_text(encoding="utf-8")
        assert "pathlib" not in imported_roots(SEMANTIC_COMPILER / name), name
        assert "open(" not in source, name


# --------------------------------------------------------------------------
# Dependency direction: requirements precede obligations.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module", ["context_requirements.py", "task_scope.py", "task_context.py"])
def test_upstream_context_stages_have_no_downstream_dependency(module: str) -> None:
    modules = imported_modules(SEMANTIC_COMPILER / module)
    assert not (modules & set(UPSTREAM_FORBIDDEN_DEPS)), module


def test_context_compilation_receives_the_authority_order_rather_than_importing_it() -> None:
    """``task_context`` must not import the execution contract compiler."""
    assert "l9_cognitive_runtime.compiler.execution" not in imported_modules(
        SEMANTIC_COMPILER / "task_context.py"
    )


# --------------------------------------------------------------------------
# INV-CTX-002: exactly one live semantic spine.
# --------------------------------------------------------------------------


def test_exactly_one_compile_pipeline_class_exists() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in PACKAGE.rglob("*.py")
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == "CompilePipeline"
    ]
    assert definitions == [THE_ONE_COMPOSITION_OWNER]


def test_only_the_pipeline_sequences_semantic_stages() -> None:
    """Constructing two or more stage owners in one module is a composition root.

    This is the check that would have caught ``compiler/context.py`` composing a
    second semantic chain: it produced IRs while bypassing context closure,
    packet validation, and liveness entirely.
    """
    offenders = {
        path.relative_to(ROOT).as_posix(): sorted(owners)
        for path in PACKAGE.rglob("*.py")
        if len(owners := instantiated_stage_owners(path)) > 1
    }
    assert offenders == {THE_ONE_COMPOSITION_OWNER: sorted(STAGE_OWNERS)}


def test_legacy_runtime_wrappers_do_not_sequence_semantic_stages() -> None:
    offenders = {
        path.relative_to(ROOT).as_posix(): sorted(owners)
        for path in python_sources(LEGACY_RUNTIME)
        if len(owners := instantiated_stage_owners(path)) > 1
    }
    assert offenders == {}


def test_the_compatibility_surface_owns_no_semantics() -> None:
    """``compiler/context.py`` delegates; it composes nothing itself."""
    assert instantiated_stage_owners(SEMANTIC_COMPILER / "context.py") == set()
    assert "CompilePipeline().compile_from_root(" in (SEMANTIC_COMPILER / "context.py").read_text(
        encoding="utf-8"
    )


def test_the_service_delegates_to_that_one_pipeline() -> None:
    service = (PACKAGE / "service.py").read_text(encoding="utf-8")
    assert "CompilePipeline().compile(" in service


# --------------------------------------------------------------------------
# INV-CTX-012: whole-snapshot resolution is a diagnostic, never a projection.
# --------------------------------------------------------------------------


def test_no_production_module_resolves_the_whole_snapshot() -> None:
    """``SnapshotResolution.resolve_all()`` is diagnostics-only.

    Resolution is destructive, so a projection that resolved every candidate
    would let claims it is not eligible to consume eliminate ones it needs, and
    would charge it with contradictions among claims it may never look at. That
    is the exact defect the deferred-resolution repair removed, and nothing at
    runtime would announce its return: a module that called ``resolve_all()``
    would compile, pass, and be wrong in the same way as before.

    The method stays public because the supersession rule itself is worth
    exercising independently of any requirement — tests do that. Production
    code has no such need, so its use anywhere under the package is the drift.
    """
    offenders = {
        path.relative_to(ROOT).as_posix(): lines
        for path in PACKAGE.rglob("*.py")
        if (lines := attribute_references(path, "resolve_all"))
    }
    assert offenders == {}


def test_that_guard_detects_a_resolve_all_call(tmp_path: Path) -> None:
    """The discriminator: an empty offender set means absence, not a blind check.

    The planted call is on a *parameter*, which is the shape a real regression
    would take and the one a guard keyed on a known receiver would miss.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def compile_context(resolution):\n    return resolution.resolve_all().groups\n",
        encoding="utf-8",
    )
    assert attribute_references(planted, "resolve_all") == [2]
    assert instantiated_stage_owners(PACKAGE / "service.py") == set()


def test_context_stages_are_owned_by_the_pipeline_not_duplicated() -> None:
    pipeline = (SEMANTIC_COMPILER / "pipeline.py").read_text(encoding="utf-8")
    for stage in (
        "TaskScopeCompiler()",
        "ContextDiscoveryCompiler()",
        "ContextRequirementPlanner()",
        "ContextCompiler()",
        "ContextClosureValidator()",
        "ObligationDeriver()",
    ):
        assert pipeline.count(stage) == 1, stage


def test_no_compatibility_entry_can_bypass_the_gates() -> None:
    """Every compile path runs closure, packet validation, and liveness once."""
    pipeline = (SEMANTIC_COMPILER / "pipeline.py").read_text(encoding="utf-8")
    for gate in (
        "ContextClosureValidator().validate(",
        "validate_packet(packet)",
        "validate_runtime_semantic_liveness(",
        "preflight_snapshot(snapshot)",
    ):
        assert pipeline.count(gate) == 1, gate
    # ...because both public entries funnel into the same private core.
    assert pipeline.count("def _compile(") == 1
    assert pipeline.count("self._compile(") == 2


# --------------------------------------------------------------------------
# INV-CTX-039: no liveness or closure check may pass vacuously.
# --------------------------------------------------------------------------


def _check_call_conditions(path: Path, function_name: str) -> list[ast.expr]:
    """The condition argument of every ``check(name, condition, details)`` call."""
    conditions: list[ast.expr] = []
    for node in ast.walk(_tree(path)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == function_name
            and len(node.args) >= 2
        ):
            conditions.append(node.args[1])
    return conditions


@pytest.mark.parametrize("module", ["liveness.py", "context_closure.py"])
def test_no_validator_check_has_a_constant_condition(module: str) -> None:
    """``check(name, True, {})`` reports a guarantee that was never evaluated."""
    constants = [
        ast.unparse(condition)
        for condition in _check_call_conditions(SEMANTIC_COMPILER / module, "check")
        if isinstance(condition, ast.Constant)
    ]
    assert constants == [], module


def test_the_liveness_validator_has_no_optional_input() -> None:
    """An optional input is a check that can be skipped when it is absent."""
    tree = _tree(SEMANTIC_COMPILER / "liveness.py")
    target = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "validate_runtime_semantic_liveness"
    )
    assert target.args.kw_defaults == [None] * len(target.args.kwonlyargs)
    assert target.args.defaults == []


@pytest.mark.parametrize(
    ("module", "ladder"),
    [("liveness.py", "_ALL_CHECKS"), ("context_closure.py", "CONTEXT_CHECKS")],
)
def test_every_declared_check_name_is_used_in_a_check_call(module: str, ladder: str) -> None:
    """A ladder entry with no corresponding call is a name without a check."""
    path = SEMANTIC_COMPILER / module
    tree = _tree(path)
    declared: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == ladder for t in node.targets
        ):
            assert isinstance(node.value, ast.Tuple)
            declared = [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
    assert declared, ladder
    called = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "check"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert set(declared) - called == set(), module


# --------------------------------------------------------------------------
# INV-CTX-041: the architecture law is present, and no dependency crept in.
# --------------------------------------------------------------------------


def test_repository_root_invariants_document_is_present_and_complete() -> None:
    invariants = ROOT / "INVARIANTS.md"
    assert invariants.is_file()
    text = invariants.read_text(encoding="utf-8")
    declared = {f"INV-CTX-{index:03d}" for index in range(1, 48)}
    missing = sorted(name for name in declared if f"### {name}:" not in text)
    assert missing == []


def test_the_compiled_context_schema_ships_with_the_contracts() -> None:
    contracts = ROOT / "contracts"
    assert (contracts / "compiled_task_context.schema.json").is_file()
    assert (contracts / "context_snapshot.schema.json").is_file()
    assert (contracts / "context_plan.schema.json").is_file()


def test_no_new_runtime_dependency_was_added() -> None:
    tomllib = pytest.importorskip("tomllib")
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {
        re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        for spec in manifest["project"]["dependencies"]
    }
    assert runtime == {"mcp", "pydantic", "pyyaml"}
