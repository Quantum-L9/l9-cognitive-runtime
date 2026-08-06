# syntax=docker/dockerfile:1.7
# Production baseline for the authenticated read-only MCP HTTP service (L9CR-MCP-012).

FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim AS builder

WORKDIR /build
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install locked runtime deps into an isolated venv; project code via PYTHONPATH (uv.package=false).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm AS runtime

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app /pack /tmp \
    && chown -R app:app /app /pack /tmp

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app src /app/src
# Pack root for provenance-bound compile (read-only mount preferred at deploy time).
COPY --chown=app:app MANIFEST.json FINAL_EXECUTION_CONTRACT.yaml EXECUTION_GRAPH.json /pack/
COPY --chown=app:app runtime /pack/runtime
COPY --chown=app:app contracts /pack/contracts

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    L9_PACK_ROOT=/pack \
    PORT=8080 \
    HOME=/app

WORKDIR /app
USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]

# Prefer deploy with: --read-only --tmpfs /tmp:rw,size=64m --cap-drop=ALL
CMD ["python", "-m", "l9_cognitive_runtime.mcp.http"]
