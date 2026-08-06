# Container deploy and rollback (L9CR-MCP-012)

Immutable, non-root image for the hosted read-only MCP HTTP service.

## Build and record digest

```bash
IMAGE=ghcr.io/quantum-l9/l9-cognitive-runtime-mcp
TAG="${IMAGE}:$(git rev-parse --short HEAD)"
docker build -t "$TAG" .
DIGEST="$(docker image inspect "$TAG" --format '{{index .RepoDigests 0}}')"
# After push:
docker push "$TAG"
DIGEST="$(docker buildx imagetools inspect "$TAG" --format '{{json .Manifest.Digest}}')"
echo "Deploy only by digest: ${IMAGE}@${DIGEST}"
```

Never promote a floating tag (`:latest`) to production. Pin `@sha256:…`.

## Runtime flags (required baseline)

```bash
docker run --detach --name l9-mcp \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  --user 10001:10001 \
  --publish 8080:8080 \
  --env PORT=8080 \
  --env L9_PACK_ROOT=/pack \
  "${IMAGE}@${DIGEST}"
```

Optional: bind-mount a verified pack root over `/pack:ro` when provenance must match a signed digest outside the image.

## Endpoint smoke

```bash
curl -fsS "http://127.0.0.1:8080/healthz"
curl -fsS "http://127.0.0.1:8080/readyz"
```

Expect `status: ok` / `status: ready` with the read-only tool list.

## Digest deployment checklist

1. CI `container-scan` job green (secrets + HIGH/CRITICAL vulns).
2. Image user is `10001:10001` (asserted in CI).
3. Record digest in the change ticket / release notes.
4. Deploy by digest only.
5. Smoke `/healthz` and `/readyz`.

## Rollback

```bash
PREV_DIGEST=sha256:…   # last known-good
docker pull "${IMAGE}@${PREV_DIGEST}"
docker rm -f l9-mcp
docker run --detach --name l9-mcp \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop=ALL --security-opt=no-new-privileges:true \
  --user 10001:10001 --publish 8080:8080 \
  "${IMAGE}@${PREV_DIGEST}"
curl -fsS "http://127.0.0.1:8080/healthz"
```

Keep the previous digest until the new revision passes smoke + pack provenance checks.

## Pack provenance

On ready hosts, compile against `L9_PACK_ROOT` and compare digests to the pack `MANIFEST.json` / loader provenance. Mismatch → fail closed; do not serve the revision.
