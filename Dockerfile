# syntax=docker/dockerfile:1.7
# Hosted MCP deployment baseline. Authentication remains a separate contract.

FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim AS builder

WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-build

COPY FINAL_EXECUTION_CONTRACT.yaml VALIDATION_CONTRACT.yaml HANDOFF_CONTRACT.yaml EXECUTION_GRAPH.json ./
COPY contracts ./contracts
COPY runtime ./runtime

ARG L9_SOURCE_REVISION
RUN test -n "$L9_SOURCE_REVISION" \
    && PYTHONPATH=/build/src /opt/venv/bin/python -m l9_cognitive_runtime.deployment \
        --source-root /build \
        --destination /opt/l9-pack \
        --source-revision "$L9_SOURCE_REVISION" \
    && PYTHONPATH=/build/src /opt/venv/bin/python -c \
        "from l9_cognitive_runtime.pack import PackLoader; PackLoader().load('/opt/l9-pack')"

FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app /tmp \
    && chown -R app:app /app /tmp

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/l9-pack /opt/l9-pack
COPY --chown=app:app src /app/src

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    L9_PACK_ROOT=/opt/l9-pack \
    L9_BIND_HOST=0.0.0.0 \
    PORT=8080 \
    HOME=/app

WORKDIR /app
USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]

CMD ["python", "-m", "l9_cognitive_runtime.mcp.http"]
