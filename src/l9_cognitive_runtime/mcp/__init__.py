"""Read-only MCP stdio server for the cognitive runtime (L9CR-MCP-008B).

Exposes the deterministic compiler over MCP stdio. Invariants:

- stdio transport only; any other transport is refused.
- An explicit pack root is required (``L9_PACK_ROOT``); there is no
  working-directory fallback and no arbitrary filesystem path is accepted.
- Every compile runs against the verified, manifest-bound pack and carries
  provenance. No tool executes shell commands, mutates the repository, or
  executes graphs — the surface is read-only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier, principal_components
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from l9_cognitive_runtime import __version__
from l9_cognitive_runtime.mcp.run_store import InMemoryRunStore, RunNotFoundError
from l9_cognitive_runtime.models.context import (
    SNAPSHOT_MAX_ITEMS,
    ContextSnapshot,
    payload_item_count,
)
from l9_cognitive_runtime.models.errors import InvalidValueError, ModelValidationError
from l9_cognitive_runtime.pack import PackLoader, RuntimePack
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

SERVER_NAME = "l9-cognitive-runtime"
DEFAULT_TASK_TYPE = "kernel_runtime_convergence"
# stdio is local and unauthenticated; a single local principal owns its runs.
# Hosted OAuth binds the principal to the token subject in MCP-011C.
LOCAL_PRINCIPAL = "local-stdio"
READ_ONLY_TOOLS = (
    "runtime_capabilities",
    "compile_intent",
    "plan_kernel_activation",
    "compile_runtime",
    "validate_runtime_bundle",
)


# Tools that accept a governed ``ContextSnapshot`` payload (INV-CTX-043).
# ``compile_intent`` is deliberately absent: intent semantics do not depend on
# governed context, so accepting it there would imply an influence it has not.
CONTEXT_AWARE_TOOLS = (
    "compile_runtime",
    "plan_kernel_activation",
    "validate_runtime_bundle",
)


def _capabilities(pack: RuntimePack, *, authentication: str = "none") -> dict[str, Any]:
    return {
        "server": SERVER_NAME,
        "version": __version__,
        "transport": "stdio",
        # Callers should be able to discover whether this surface is protected
        # without having to provoke a 401 to find out.
        "authentication": authentication,
        "mode": "read_only",
        "tools": list(READ_ONLY_TOOLS),
        "writes": False,
        "execution": False,
        "shell": False,
        # INV-CTX-043: governed context is useless if callers cannot discover
        # that this surface accepts it.
        "context_snapshot_input": True,
        "context_aware_tools": list(CONTEXT_AWARE_TOOLS),
        "pack_ref": pack.provenance.pack_ref,
        "manifest_digest": pack.provenance.manifest_digest,
    }


def parse_context_snapshot(payload: dict[str, Any] | None) -> ContextSnapshot | None:
    """Validate a governed context payload, or fail closed.

    ``None`` means no governed snapshot, which is the empty governed snapshot
    every pre-context caller already gets. A *malformed* payload is not the same
    thing and must never be silently downgraded to it.
    """
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise InvalidValueError("context_snapshot must be an object", path="context_snapshot")
    # The item ceiling is applied to the untyped payload: typing a candidate
    # derives its identity, which hashes it, so counting first is what keeps an
    # oversized payload from being hashed before it is refused (INV-CTX-007).
    count = payload_item_count(payload)
    if count > SNAPSHOT_MAX_ITEMS:
        raise InvalidValueError(
            "context_snapshot exceeds the maximum item count",
            path="context_snapshot",
            details={"items": count, "max_items": SNAPSHOT_MAX_ITEMS},
        )
    try:
        return ContextSnapshot.from_mapping(payload)
    except ModelValidationError as exc:
        raise InvalidValueError(
            f"context_snapshot is not a valid governed snapshot: {exc}",
            path="context_snapshot",
        ) from exc


def resolve_principal(*, hosted_auth: bool) -> str | None:
    """Resolve the run-owning principal, or ``None`` when identity is unknown.

    Hosted requests are owned by the validated token's ``(client_id, issuer,
    subject)`` triple — the same components the SDK binds session ownership to, so
    two users of one OAuth client are distinct principals. Local stdio has no token
    and is owned by ``LOCAL_PRINCIPAL``.

    The two must never meet. Under hosted auth a request without a validated token
    returns ``None`` rather than falling back to ``LOCAL_PRINCIPAL``, which would
    hand an unauthenticated caller the local principal's runs. The SDK's
    ``RequireAuthMiddleware`` should already have rejected such a request; this is
    the second lock on the same door.

    Lives at module level rather than inside ``build_server`` so the rule can be
    read and tested on its own — it is the one place run ownership is decided.
    """
    token = get_access_token()
    if token is not None:
        return "oauth:" + json.dumps(principal_components(token), separators=(",", ":"))
    if hosted_auth:
        return None
    return LOCAL_PRINCIPAL


def build_server(
    pack_root: Path,
    *,
    token_verifier: TokenVerifier | None = None,
    auth_settings: AuthSettings | None = None,
) -> MCPServer:
    """Create a read-only MCP server bound to an explicit, verified pack root.

    ``token_verifier``/``auth_settings`` switch the server into hosted
    resource-server mode (MCP-011): the SDK then requires a validated bearer token
    on the HTTP transport and every run is owned by the token's principal. Both
    default to ``None``, which is the local stdio posture — unauthenticated, owned
    by ``LOCAL_PRINCIPAL``. Authentication changes *who owns a run*; it never
    changes what the compiler produces.
    """
    root = pack_root.resolve()
    if not root.is_dir():
        raise InvalidValueError("pack_root must be an existing directory", path=str(root))
    # Fail closed at startup: the pack must load and verify.
    pack = PackLoader().load(root)
    pack_ref = str(pack.manifest.get("pack_name") or root.name)
    service = CognitiveRuntimeService()
    runs = InMemoryRunStore()

    def _compile(
        mission: str,
        task_type: str = DEFAULT_TASK_TYPE,
        context_snapshot: dict[str, Any] | None = None,
    ) -> Any:
        # ``ModelValidationError`` is this runtime's typed *anticipated* failure:
        # the caller supplied something the contract refuses. The SDK classifies
        # any exception that is not ``ToolError`` as a server crash, replacing the
        # message with "Error executing tool <name>" and logging a traceback — so
        # without this translation a malformed ``context_snapshot`` still fails
        # closed (INV-CTX-043) but stops saying *what* was wrong. Re-raising as
        # ``ToolError`` restores the diagnosis to the caller and keeps genuine
        # bugs classified as crashes, which is stricter than the 2.0.0 surface
        # that passed every exception's text through.
        try:
            return service.compile_runtime(
                CompileRequest(mission=mission, task_type=task_type, pack_root=root),
                context_snapshot=parse_context_snapshot(context_snapshot),
            )
        except ModelValidationError as exc:
            raise ToolError(str(exc)) from exc

    def _require_bound_pack(requested: str) -> None:
        if requested != pack_ref:
            raise InvalidValueError("unknown pack_ref", path=requested)

    def _read_pack_file(relative: str) -> str:
        # pack.resolve confines beneath the pack root and rejects traversal.
        return pack.resolve(relative).read_text(encoding="utf-8")

    hosted_auth = token_verifier is not None and auth_settings is not None
    auth_mode = "oauth2_bearer" if hosted_auth else "none"

    mcp = MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=(
            "Read-only L9 Cognitive Runtime MCP. Compiles runtime bundles in memory "
            "against a verified pack; does not execute graphs, run shell commands, or "
            "mutate the repository."
        ),
        token_verifier=token_verifier,
        auth=auth_settings,
    )

    @mcp.tool()
    def runtime_capabilities() -> dict[str, Any]:
        """List the read-only capabilities of this MCP server."""
        return _capabilities(pack, authentication=auth_mode)

    @mcp.tool()
    def compile_intent(mission: str, task_type: str = DEFAULT_TASK_TYPE) -> dict[str, Any]:
        """Compile the canonical intent contract for a mission (read-only)."""
        bundle = _compile(mission, task_type)
        return {
            "intent": bundle.intent.to_canonical_dict(),
            "intent_digest": bundle.digests()["intent"],
        }

    @mcp.tool()
    def plan_kernel_activation(
        mission: str, context_snapshot: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return the contract's kernel activation plan (read-only).

        Accepts a governed context snapshot because context can change routing:
        a governed architecture constraint is what proves materiality, and
        materiality pulls the architecture phase and kernel into the plan.
        """
        bundle = _compile(mission, context_snapshot=context_snapshot)
        return {
            "kernel_activation": list(bundle.execution.kernel_activation),
            "execution_sequence": list(bundle.execution.execution_sequence),
            "execution_digest": bundle.digests()["execution"],
            "context_digest": bundle.digests()["context"],
        }

    @mcp.tool()
    def compile_runtime(
        mission: str,
        task_type: str = DEFAULT_TASK_TYPE,
        context_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compile a full runtime bundle in memory and store an isolated run.

        ``context_snapshot`` is the governed context input (INV-CTX-043). It is
        typed and validated before compilation; an invalid payload fails closed.
        """
        bundle = _compile(mission, task_type, context_snapshot=context_snapshot)
        # Store only the derived result — never raw request/intent/kernel bodies.
        payload = {
            "digests": bundle.digests(),
            "execution_contract_id": bundle.execution.contract_id,
            "graph_id": bundle.graph.graph_id,
            "terminal_node": bundle.graph.terminal_node,
            "provenance": bundle.provenance.to_dict(),
            # A0703: the full compiled execution packet is an immutable
            # per-run artifact resolvable through l9://runs/{run_id}.
            "execution_packet": bundle.packet,
        }
        owner = resolve_principal(hosted_auth=hosted_auth)
        if owner is None:
            # Hosted transport with no validated identity: refuse rather than
            # create a run nobody can be held to own.
            raise ToolError("authenticated principal required")
        record = runs.create(principal=owner, payload=payload)
        return {**payload, "run_id": record.run_id, "resource_uri": record.resource_uri}

    @mcp.tool()
    def validate_runtime_bundle(
        mission: str, context_snapshot: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Compile and validate a runtime bundle's integrity (read-only)."""
        bundle = _compile(mission, context_snapshot=context_snapshot)
        digests = bundle.digests()
        packet_context = bundle.packet.get("compiled_task_context_digest")
        checks = {
            "all_digests_present": all(digests.values()),
            "graph_has_terminal": bool(bundle.graph.terminal_node),
            "provenance_present": bundle.provenance is not None,
            # INV-CTX-030: the packet's context identity agrees with the bundle's.
            "packet_context_digest_matches": packet_context == digests["context"],
        }
        return {"valid": all(checks.values()), "digests": digests, "checks": checks}

    @mcp.resource("l9://runtime/version")
    def runtime_version_resource() -> str:
        return __version__

    @mcp.resource("l9://runtime/capabilities")
    def runtime_capabilities_resource() -> str:
        return json.dumps(
            _capabilities(pack, authentication=auth_mode),
            indent=2,
            sort_keys=True,
        )

    @mcp.resource("l9://packs/{pack_ref}/manifest")
    def pack_manifest_resource(pack_ref: str) -> str:
        _require_bound_pack(pack_ref)
        return json.dumps(
            {
                "pack_ref": pack.provenance.pack_ref,
                "manifest_digest": pack.provenance.manifest_digest,
                "files": dict(pack.provenance.file_digests),
            },
            indent=2,
            sort_keys=True,
        )

    @mcp.resource("l9://packs/{pack_ref}/schemas/{schema_name}")
    def pack_schema_resource(pack_ref: str, schema_name: str) -> str:
        _require_bound_pack(pack_ref)
        return _read_pack_file(f"schemas/{schema_name}")

    @mcp.resource("l9://packs/{pack_ref}/kernels/{kernel_id}")
    def pack_kernel_resource(pack_ref: str, kernel_id: str) -> str:
        _require_bound_pack(pack_ref)
        return _read_pack_file(f"kernels/{kernel_id}")

    @mcp.resource("l9://runs/{run_id}")
    def run_resource(run_id: str) -> str:
        # Anti-enumerating: unknown, expired, cross-principal and (under hosted
        # auth) unidentified callers all raise the same RunNotFoundError, so a
        # reader cannot tell "not yours" from "does not exist".
        owner = resolve_principal(hosted_auth=hosted_auth)
        if owner is None:
            raise RunNotFoundError("run not found", path=run_id)
        record = runs.require(run_id, owner)
        return json.dumps(record.payload, indent=2, sort_keys=True)

    return mcp


def main() -> None:
    """Stdio-only entrypoint. Non-stdio transports and missing pack roots are refused."""
    transport = os.environ.get("L9_MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        print("error: only stdio transport is supported (L9CR-MCP-008B)", file=sys.stderr)
        raise SystemExit(2)
    pack_root = os.environ.get("L9_PACK_ROOT")
    if not pack_root:
        print(
            "error: L9_PACK_ROOT is required (no working-directory fallback)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    server = build_server(Path(pack_root))
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
