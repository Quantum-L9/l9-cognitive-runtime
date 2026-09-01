# FINAL FINDINGS — release-staging

Phase 4 of `l9cr_straight_line_chatgpt_mcp_deploy` v1.0.0.

## Terminal verdict: BLOCKED — upstream defect in `l9-ci-core`, not in this repository

The historical failure is **not** historical. It reproduces today, on current pinned
Core, and it is structural: the canonical release gate runs the SDK in strict mode
without supplying the identity map strict mode requires, so **any** semgrep finding
fails the release. The repository cannot fix this from its side, because Core exposes
no input through which to supply one.

No image was published. No staging deployment was dispatched. Neither is claimed.

## Revisions

| Field | Value |
|---|---|
| `origin/main` | `28f5b4b2450299de34f2d2d69bea32ece09363b1` |
| Branch under test | `claude/l9-chatgpt-mcp-deploy-vpevgd` |
| Core pinned by this repo | `6d5507245cd01d915e3bf400a1e4f8c31ed95e3c` |
| Core `main` today | `aaa01124d95b8fc51369636116e71aedf2f7389f` |
| Core revision siblings' pack recommends | `54a2f2fc8d060674d544fab14388bb5eff6b8e78` |

## Reproduction — three runs, and what their arithmetic proves

`release-staging.yml` was dispatched twice on the feature branch. The `release` job is
guarded by `github.ref == 'refs/heads/main'`, so on a feature branch it is **skipped**:
these runs exercise the gate and can neither publish an image nor dispatch a deployment.
Both runs confirm the `release` job's conclusion as `skipped`.

| # | Run | Revision | Result | Unresolved fingerprints |
|---|---|---|---|---|
| 1 | [32545475954](https://github.com/Quantum-L9/l9-cognitive-runtime/actions/runs/32545475954) (2026-08-22, `main`) | `45d87e9` | failure | **1** — `fn_semgrep_361ffc3c…` |
| 2 | [33553078058](https://github.com/Quantum-L9/l9-cognitive-runtime/actions/runs/33553078058) | `955128d` | failure | **2** — `fn_semgrep_43615612…`, `fn_semgrep_ed57f590…` |
| 3 | [33553458900](https://github.com/Quantum-L9/l9-cognitive-runtime/actions/runs/33553458900) | `989d352` | failure | **1** — `fn_semgrep_2720af98…` |

Every run fails identically:

```
error[unresolved_strict_contract]: strict identity resolution failed for findings: …
Process completed with exit code 6
```

in step **"Run + normalize semgrep (SDK)"**, before `Validate canonical bundle`,
`Evaluate gate`, publish, or dispatch — all of which are skipped.

**The 1 → 2 → 1 sequence is the diagnosis.** Between runs 1 and 2 this branch added
exactly one semgrep finding (see below) and the unresolved count rose by exactly one;
run 3 removed that finding and the count fell back by exactly one. The unresolved count
tracks the *total* finding count one-for-one. Nothing resolves. This is not a stale map
missing a few new registry rules — it is no map at all.

The job environment confirms it directly:

```
L9_IDENTITY_MAP:            <empty>
L9_POLICY:                  <empty>
L9_STRICT: true
L9_REQUIRED: true
```

## Root cause and ownership: CI_CORE_DEFECT

Strict mode demands that every finding's provider rule id resolve to a canonical
identity. The map that performs that resolution is never delivered to the SDK:

1. **Core does not wire it.** `analyze-semgrep.yml` passes `policy` (from
   `resolve-governance`'s `sdk-policy` output) to `invoke-sdk`, but passes **no**
   `identity-map` — at the pinned revision `6d55072` *and* at Core `main` today.
   `invoke-sdk` accepts an `identity-map` input; `analyze-semgrep.yml` never sets it.
2. **`resolve-governance` cannot supply it.** Its outputs are `sdk-profile`, `mode`,
   `enabled`, `strict`, `required-provider`, `sdk-policy`, `waiver-ids`,
   `governance-digest`. There is no identity-map output.
3. **The consumer contract has no slot for it.** Core's own instantiation pack README
   (shipped in `l9-ci-debt-lsp` / `l9-ci-debt-resolver`) states the pack is **exactly six
   files** — `execution-profiles`, `provider-requiredness`, `rule-modes`, `waivers`,
   `promotion-policy`, `quality-thresholds` — and that for `quality-thresholds`,
   "Empty = no policy" is valid. `semgrep-identity-map.yaml` is not among them.
4. **The map exists only as a preset artifact.** `presets/python/.github/governance/semgrep-identity-map.yaml`
   is 33 KB of rule → canonical-id mappings, and Core passes it explicitly **only** in
   its own `sdk-contract-check.yml` self-test. Keeping it current is documented as
   "Control-plane authority; **not Core**" (`tools/regenerate_identity_maps.py`).

So the `release` profile sets `strict: true` and `semgrep: required: true`, and Core
then invokes the SDK in a configuration that cannot satisfy strict mode. The gate is
unpassable by construction for any repository with at least one finding.

### This repository's governance pack is correct

`.github/governance/` here contains exactly the six contract files. Verified against
Core's preset and against the two sibling consumers that adopted the same pack
(`l9-ci-debt-lsp`, `l9-ci-debt-resolver`) — **neither** ships an identity map or a
policy file either, and both use `sdk_policy: ""`. This repo is not misconfigured, and
it is not an outlier.

### Why no repo-side change was made

The contract is explicit: *"Fix the defect in the repository that owns it. Do not patch
l9-cognitive-runtime to compensate for an upstream CI bug unless the consumer contract
explicitly requires a repo-side declaration."* The consumer contract requires no such
declaration, so no compensating change was made and no ceremonial PR was opened.

Two tempting non-fixes were considered and rejected:

- **Copying the preset's `semgrep-policy.yaml` in and pointing `sdk_policy` at it.**
  That policy sets `defaults.mode: advisory` for everything. It would likely turn the
  release gate green — by making every semgrep finding non-blocking at release. That is
  weakening a release security gate, which `governance_lock` forbids
  (`strict_release: true`, `bypass: FORBIDDEN`). It is also the wrong lever: the failure
  is identity *resolution*, which happens in `semgrep run` before any policy is applied.
- **Adding a waiver.** `governance_lock` permits one only where an authoritative process
  requires it and the finding is proven not to be a real defect. Neither holds, and a
  waiver would mask a Core wiring gap rather than record it.

## The one repo-side finding, found and fixed

Independent of the Core defect: this branch's new `mcp/auth.py` tripped
`python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure`
on the string literal `"bearer token rejected (%s)"`. The rule matches the *literal*, not
the arguments — only an exception class name is ever logged. On a repository whose
`p/python` baseline was zero findings, this was the first.

Reworded at the source rather than waived; re-verified with the CI-pinned semgrep
(1.171.0, `--config p/python`): **1 finding before, 0 after**, matching the pre-change
baseline. Run 3 above is the independent confirmation in CI.

**Net effect of this branch on the release gate: zero added findings.**

## Required release proof — status

| Requirement | Status |
|---|---|
| release Semgrep passed | **FAILED** — `unresolved_strict_contract`, exit 6 |
| strict identity resolution passed | **FAILED** — the defect itself |
| canonical analysis publish passed | **SKIPPED** (blocked by the above) |
| immutable image published | **NOT REACHED** |
| image digest recorded | **UNKNOWN — no image exists** |
| SBOM / provenance attestation | **NOT REACHED** (required by `.l9/deployment.yaml`) |
| staging deployment request sent | **NOT REACHED** |
| deployment reports healthy | **UNKNOWN** |
| MCP initialize / runtime_capabilities / compile_runtime on staging | **UNKNOWN** |
| deployed digest and pack provenance agree | **UNKNOWN** |

`mcp-staging.quantumaipartners.com` appears in `.l9/deployment.yaml`. A hostname in a
manifest is not a live service; no request was made to it and none is reported.

## Recommended fix, in the repository that owns it

In `Quantum-L9/l9-ci-core`, one of:

1. **Wire the identity map through the pipeline** (preferred). Add an `identity-map`
   output to `resolve-governance` (resolving `<governance-root>/semgrep-identity-map.yaml`
   when present, else the language preset's copy), and pass it from
   `analyze-semgrep.yml` to `invoke-sdk`, which already accepts the input. Then add the
   file to the consumer pack and its README, making it a seventh contract file.
2. **Package the map in the SDK** so `l9-ci semgrep run --strict` resolves without an
   explicit flag, and keep it synced by the existing control-plane job
   (`tools/regenerate_identity_maps.py`).

Either way, `sdk-contract-check.yml` should gain a case that runs a consumer-shaped
repository with ≥1 finding through `analyze-semgrep.yml` at `profile: release`. Core's
current self-test passes `--identity-map` explicitly, which is precisely why it never
caught the gap the real consumer path has.

Until then, `release-staging` cannot publish for this repository, and the same is true
for every other consumer of this pipeline.

## Unresolved UNKNOWNs

- Whether a newer Core revision fixes this — **UNKNOWN**. Core `main` (`aaa01124`)
  still does not pass `identity-map` in `analyze-semgrep.yml`, so a pin bump alone
  looks insufficient, but this was not proven by running against it.
- What the residual finding on a clean tree actually is — **UNKNOWN**. Local
  `p/python` reports zero; the SDK runs the registry ruleset *plus* a packaged L9
  ruleset, and the bundle artifact that would name the rule is not produced because the
  run fails before `Route artifacts`.
- Whether the deployment broker, `DEPLOYMENT_BROKER_TOKEN`, and the registered profile
  at `integrations/consumers/l9-cognitive-runtime.deployment.yaml` are correctly
  provisioned — **UNKNOWN**, never reached.
