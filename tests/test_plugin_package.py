"""Private Agent Plugin package for the existing read-only MCP server (issue #61).

The plugin is guidance and packaging only. These tests prove it stays that way:
the manifest conforms to the portable Agent Plugins 1.0.0 schema, the single
skill conforms to Agent Skills, every tool call the skill documents exists on
the real server with real argument names, the documented workflow compiles
against a verified pack, and missing connection or invalid context fails closed.
"""

from __future__ import annotations

import asyncio
import json
import re
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from mcp.server.mcpserver.exceptions import ToolError

from l9_cognitive_runtime.mcp import READ_ONLY_TOOLS, build_server, main
from l9_cognitive_runtime.models.errors import InvalidValueError

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "l9-cognitive-runtime"
SKILLS = PLUGIN / "skills"
MISSION = "Update greeting text."

# Agent Plugins 1.0.0 manifest schema, verbatim from
# https://agent-plugins.org/schemas/1.0.0/plugin.schema.json. Inlined because the
# specification forbids fetching the schema at load time and tests run offline.
PLUGIN_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    "type": "object",
    "properties": {
        "$schema": {"const": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"},
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 64,
            "pattern": "^(?!.*(?:--|\\.\\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
        },
        "version": {"type": "string"},
        "description": {"type": "string"},
        "author": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "url": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "homepage": {"type": "string"},
        "repository": {"type": "string"},
        "license": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "extensions": {"type": "object", "additionalProperties": {"type": "object"}},
    },
    "required": ["$schema", "name"],
    "additionalProperties": False,
}

# Agent Skills (agentskills.io/specification) frontmatter rules.
SKILL_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
SKILL_NAME = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
# A documented tool call, e.g. `compile_runtime(mission, task_type?)`.
TOOL_CALL = re.compile(r"`([a-z_]+)\(([^)`]*)\)`")


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=15))


def _tool_data(result: Any) -> dict[str, Any]:
    assert result.is_error is False, getattr(result, "content", result)
    if getattr(result, "structured_content", None):
        return cast("dict[str, Any]", result.structured_content)
    return cast("dict[str, Any]", json.loads(result.content[0].text))


def _manifest() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((PLUGIN / "plugin.json").read_text("utf-8")))


def _skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())


def _skill() -> tuple[dict[str, Any], str]:
    (skill_dir,) = _skill_dirs()
    text = (skill_dir / "SKILL.md").read_text("utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert match, "SKILL.md must open with YAML frontmatter"
    return cast("dict[str, Any]", yaml.safe_load(match.group(1))), match.group(2)


def _documented_calls() -> list[tuple[str, set[str]]]:
    _, body = _skill()
    return [
        (name, {a.strip().rstrip("?") for a in raw.split(",") if a.strip()})
        for name, raw in TOOL_CALL.findall(body)
    ]


# --- package structure -------------------------------------------------------


def test_manifest_is_schema_valid_and_identity_consistent() -> None:
    manifest = _manifest()
    errors = sorted(Draft202012Validator(PLUGIN_SCHEMA).iter_errors(manifest), key=str)
    assert not errors, [e.message for e in errors]

    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    assert manifest["name"] == PLUGIN.name == project["name"]
    assert manifest["version"] == project["version"]


def test_exactly_one_spec_conformant_skill() -> None:
    dirs = _skill_dirs()
    assert [p.name for p in dirs] == ["compile-runtime-bundle"]
    assert sorted(p.name for p in SKILLS.iterdir()) == [p.name for p in dirs]

    front, body = _skill()
    assert set(front) <= SKILL_FIELDS
    assert front["name"] == dirs[0].name
    assert len(front["name"]) <= 64
    assert SKILL_NAME.match(front["name"])
    assert isinstance(front["description"], str)
    assert 0 < len(front["description"]) <= 1024
    assert 0 < len(front.get("compatibility", "x")) <= 500
    assert body.strip()


def test_package_ships_no_connection_config_endpoint_or_credential() -> None:
    files = [p for p in PLUGIN.rglob("*") if p.is_file()]
    names = {p.name for p in files}
    # Connection is operator-owned: no MCP/app binding is invented here.
    assert not names & {"mcp.json", ".mcp.json", ".app.json"}
    assert "extensions" not in _manifest()

    allowed_hosts = {
        "agent-plugins.org",
        "agentskills.io",
        "developers.openai.com",
        "github.com",
    }
    credential = re.compile(
        r"eyJ[A-Za-z0-9_-]{10,}|-----BEGIN|\bsk-[A-Za-z0-9]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}"
        r"|client_?secret\s*[:=]|\"clientId\"",
        re.IGNORECASE,
    )
    for path in files:
        text = path.read_text("utf-8")
        hosts = set(re.findall(r"https?://([^/\s)`>\"]+)", text))
        assert hosts <= allowed_hosts, (path, hosts - allowed_hosts)
        assert not credential.search(text), path


# --- skill ↔ real MCP surface ------------------------------------------------


def test_skill_documents_exactly_the_real_tools_with_real_arguments(valid_pack: Path) -> None:
    tools = {t.name: t.input_schema for t in _run(build_server(valid_pack).list_tools())}
    calls = _documented_calls()

    assert {name for name, _ in calls} == set(tools) == set(READ_ONLY_TOOLS)
    # Every mention is checked on its own: one complete call elsewhere must not
    # excuse another that omits a required argument.
    for name, args in calls:
        properties = set(tools[name].get("properties", {}))
        required = set(tools[name].get("required", []))
        assert args <= properties, (name, args - properties)
        assert required <= args, (name, required - args)


def test_documented_workflow_compiles_plan_bound_and_verifiable(valid_pack: Path) -> None:
    server = build_server(valid_pack)

    capabilities = _tool_data(_run(server.call_tool("runtime_capabilities", {})))
    assert capabilities["mode"] == "read_only"
    assert capabilities["writes"] is False
    assert capabilities["execution"] is False
    assert capabilities["shell"] is False

    planned = _tool_data(_run(server.call_tool("plan_context_requirements", {"mission": MISSION})))
    plan_id = planned["context_plan_id"]

    compiled = _tool_data(
        _run(
            server.call_tool(
                "compile_runtime", {"mission": MISSION, "expected_context_plan_id": plan_id}
            )
        )
    )
    digests = compiled["digests"]
    assert compiled["context_plan_id"] == plan_id
    assert digests["manifest"] == capabilities["manifest_digest"]
    assert compiled["provenance"]["manifest_digest"] == capabilities["manifest_digest"]
    assert compiled["execution_packet"]["compiled_task_context_digest"] == digests["context"]
    assert all(digests.values())
    assert compiled["resource_uri"] == f"l9://runs/{compiled['run_id']}"

    validated = _tool_data(_run(server.call_tool("validate_runtime_bundle", {"mission": MISSION})))
    assert validated["valid"] is True


# --- fail closed -------------------------------------------------------------


def test_missing_pack_root_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["scripts"]
    assert scripts["l9-cognitive-runtime-mcp"] == "l9_cognitive_runtime.mcp:main"
    monkeypatch.delenv("L9_MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("L9_PACK_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_unverifiable_pack_root_refuses_to_start(tmp_path: Path) -> None:
    with pytest.raises(InvalidValueError):
        build_server(tmp_path / "absent")


def test_stale_context_plan_requires_replan(valid_pack: Path) -> None:
    call = build_server(valid_pack).call_tool(
        "compile_runtime",
        {"mission": MISSION, "expected_context_plan_id": "context-plan.sha256:stale"},
    )
    with pytest.raises(ToolError, match="replan required"):
        _run(call)


def test_malformed_context_snapshot_is_refused(valid_pack: Path) -> None:
    call = build_server(valid_pack).call_tool(
        "compile_runtime", {"mission": MISSION, "context_snapshot": {"bogus": 1}}
    )
    with pytest.raises(ToolError, match="not a valid governed snapshot"):
        _run(call)
