"""Release gate script evidence (L9CR-MCP-014)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_mcp_release_gate.py"


def test_example_metadata_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK), str(ROOT / "release/mcp-release-metadata.example.json")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_incomplete_metadata_fails(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"release_id": "x"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CHECK), str(bad)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "FAIL" in result.stdout
