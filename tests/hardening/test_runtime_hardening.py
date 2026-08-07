"""Runtime hardening suites: golden, determinism, concurrency, path safety.

Compiles run against the ``valid_pack`` fixture (a manifest-verified pack); the
fail-closed service will not compile against the mutable repository root.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path

import pytest

from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.pack import PackLoader
from l9_cognitive_runtime.parsing import StrictParseError, load_yaml_mapping
from l9_cognitive_runtime.service import CognitiveRuntimeService, CompileRequest

WORKLOADS = (
    "audit kernel pack for stub drift",
    "compile intent into execution graph",
    "prepare adapter handoff without mutation",
)


@pytest.mark.parametrize("mission", WORKLOADS)
def test_golden_bundle_digests_stable(mission: str, valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    first = service.compile_runtime(CompileRequest(mission=mission, pack_root=valid_pack))
    second = service.compile_runtime(CompileRequest(mission=mission, pack_root=valid_pack))
    assert first.digests() == second.digests()
    assert first.graph.sha256() == second.graph.sha256()


def test_determinism_across_repeated_compiles(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()
    digests = [
        service.compile_runtime(
            CompileRequest(mission="determinism workload", pack_root=valid_pack)
        ).digests()
        for _ in range(5)
    ]
    assert all(d == digests[0] for d in digests)


def test_concurrency_compile_isolation(valid_pack: Path) -> None:
    service = CognitiveRuntimeService()

    def _run(idx: int) -> tuple[str, str]:
        bundle = service.compile_runtime(
            CompileRequest(mission=f"concurrent-{idx}", pack_root=valid_pack)
        )
        # Intent digests differ by mission; graph shares the pack execution contract.
        return bundle.digests()["intent"], bundle.digests()["graph"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_run, range(8)))
    assert len(results) == 8
    intent_digests = {item[0] for item in results}
    assert len(intent_digests) == 8
    assert all(item[1] for item in results)


def test_path_traversal_rejected(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("ok\n", encoding="utf-8")
    digest = hashlib.sha256((tmp_path / "ok.txt").read_bytes()).hexdigest()
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps({"files": [{"path": "ok.txt", "sha256": digest}]}),
        encoding="utf-8",
    )
    pack = PackLoader().load(tmp_path)
    with pytest.raises(InvalidValueError):
        pack.resolve("../../etc/passwd")


def test_strict_parse_blocks_malformed() -> None:
    with pytest.raises(StrictParseError):
        load_yaml_mapping("bad: [\n")
