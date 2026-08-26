"""Runtime-level tests for the central compile observer lifecycle seam."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import httpx2 as httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from l9_cognitive_runtime.cli import main as cli_main
from l9_cognitive_runtime.mcp import build_server
from l9_cognitive_runtime.mcp.http import create_http_app
from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.service import (
    CognitiveRuntimeService,
    CompileRequest,
    RuntimeBundle,
    RuntimeInvocationContext,
)


class _Session:
    def __init__(self) -> None:
        self.succeeded_calls = 0
        self.failed_calls = 0
        self.succeeded_bundle: RuntimeBundle | None = None
        self.failed_error: Exception | None = None

    def succeeded(self, bundle: RuntimeBundle) -> None:
        self.succeeded_calls += 1
        self.succeeded_bundle = bundle

    def failed(self, error: Exception) -> None:
        self.failed_calls += 1
        self.failed_error = error


class _Observer:
    def __init__(self) -> None:
        self.start_calls = 0
        self.request: CompileRequest | None = None
        self.context: RuntimeInvocationContext | None = None
        self.session = _Session()

    def start(self, request: CompileRequest, context: RuntimeInvocationContext) -> _Session:
        self.start_calls += 1
        self.request = request
        self.context = context
        return self.session


class _Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, Exception]] = []

    def __call__(self, phase: str, error: Exception) -> None:
        self.events.append((phase, error))


class _StartRaisingObserver:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def start(self, request: CompileRequest, context: RuntimeInvocationContext) -> _Session:
        del request, context
        raise self.error


class _RaisingSession(_Session):
    def __init__(self, *, success_error: Exception | None, failure_error: Exception | None) -> None:
        super().__init__()
        self.success_error = success_error
        self.failure_error = failure_error

    def succeeded(self, bundle: RuntimeBundle) -> None:
        super().succeeded(bundle)
        if self.success_error is not None:
            raise self.success_error

    def failed(self, error: Exception) -> None:
        super().failed(error)
        if self.failure_error is not None:
            raise self.failure_error


class _RaisingObserver:
    def __init__(self, session: _RaisingSession) -> None:
        self.session = session

    def start(self, request: CompileRequest, context: RuntimeInvocationContext) -> _RaisingSession:
        del request, context
        return self.session


def _run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=30))


def _tool_data(result: Any) -> dict[str, Any]:
    assert result.is_error is False, getattr(result, "content", result)
    if getattr(result, "structured_content", None):
        return cast("dict[str, Any]", result.structured_content)
    return cast("dict[str, Any]", json.loads(result.content[0].text))


def test_service_success_notifies_once_with_real_bundle(valid_pack: Path) -> None:
    observer = _Observer()
    context = RuntimeInvocationContext(
        trace_id="trace-upstream",
        parent_span_id="span-parent",
        program_id="program-1",
        campaign_id="campaign-1",
        task_id="task-1",
        run_id="run-1",
        attempt_id="attempt-1",
        session_id="session-1",
    )
    service = CognitiveRuntimeService(observer=observer)
    bundle = service.compile_runtime(
        CompileRequest(mission="observed compile", pack_ref=valid_pack),
        invocation_context=context,
    )
    assert isinstance(bundle, RuntimeBundle)
    assert observer.start_calls == 1
    assert observer.context == context
    assert observer.session.succeeded_calls == 1
    assert observer.session.failed_calls == 0
    assert observer.session.succeeded_bundle is bundle


def test_service_failure_notifies_once_and_preserves_original_exception() -> None:
    observer = _Observer()
    service = CognitiveRuntimeService(observer=observer)
    with pytest.raises(InvalidValueError) as caught:
        service.compile_runtime(CompileRequest(mission="", pack_ref=Path("unused")))
    assert observer.start_calls == 1
    assert observer.session.succeeded_calls == 0
    assert observer.session.failed_calls == 1
    assert observer.session.failed_error is caught.value


def test_observer_start_failure_cannot_break_successful_compile(valid_pack: Path) -> None:
    observer_error = RuntimeError("observer start failed")
    reporter = _Reporter()
    service = CognitiveRuntimeService(
        observer=_StartRaisingObserver(observer_error),
        observer_error_reporter=reporter,
    )
    bundle = service.compile_runtime(CompileRequest(mission="still compile", pack_ref=valid_pack))
    assert isinstance(bundle, RuntimeBundle)
    assert reporter.events == [("start", observer_error)]


def test_success_notification_failure_cannot_replace_bundle(valid_pack: Path) -> None:
    observer_error = RuntimeError("observer success failed")
    session = _RaisingSession(success_error=observer_error, failure_error=None)
    reporter = _Reporter()
    service = CognitiveRuntimeService(
        observer=_RaisingObserver(session),
        observer_error_reporter=reporter,
    )
    bundle = service.compile_runtime(
        CompileRequest(mission="compile survives", pack_ref=valid_pack)
    )
    assert isinstance(bundle, RuntimeBundle)
    assert session.succeeded_bundle is bundle
    assert reporter.events == [("succeeded", observer_error)]


def test_failure_notification_failure_cannot_replace_business_error() -> None:
    observer_error = RuntimeError("observer failure failed")
    session = _RaisingSession(success_error=None, failure_error=observer_error)
    reporter = _Reporter()
    service = CognitiveRuntimeService(
        observer=_RaisingObserver(session),
        observer_error_reporter=reporter,
    )
    with pytest.raises(InvalidValueError) as caught:
        service.compile_runtime(CompileRequest(mission="", pack_ref=Path("unused")))
    assert session.failed_error is caught.value
    assert reporter.events == [("failed", observer_error)]


def test_cli_uses_the_same_central_observer(
    valid_pack: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observer = _Observer()
    context = RuntimeInvocationContext(trace_id="trace-cli", task_id="task-cli")
    assert (
        cli_main(
            ["--mission", "cli observed", "--pack-root", str(valid_pack)],
            observer=observer,
            invocation_context=context,
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["intent"]["mission"] == "cli observed"
    assert observer.start_calls == 1
    assert observer.context == context
    assert observer.session.succeeded_calls == 1


def test_mcp_uses_central_observer_without_promoting_resource_run_id(valid_pack: Path) -> None:
    observer = _Observer()
    context = RuntimeInvocationContext(trace_id="trace-mcp")
    server = build_server(
        valid_pack,
        observer=observer,
        invocation_context_factory=lambda mission, task_type: context,
    )
    result = _run(server.call_tool("compile_runtime", {"mission": "mcp observed"}))
    data = _tool_data(result)
    assert data["run_id"]
    assert observer.start_calls == 1
    assert observer.session.succeeded_calls == 1
    assert observer.context == context
    assert observer.context.run_id is None


def test_http_uses_the_same_central_observer(valid_pack: Path) -> None:
    observer = _Observer()
    app = create_http_app(valid_pack, observer=observer)

    async def scenario() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://localhost"
            ) as client:
                async with streamable_http_client(
                    "http://localhost/v1/mcp", http_client=client
                ) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "compile_runtime", {"mission": "http observed"}
                        )
                        assert result.is_error is False

    _run(scenario())
    assert observer.start_calls == 1
    assert observer.session.succeeded_calls == 1
