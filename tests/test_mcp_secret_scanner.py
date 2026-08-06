"""Secret scanner fail/pass evidence for MCP client configs (L9CR-MCP-013)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "scan_mcp_secrets.py"


def _run(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), *[str(p) for p in paths]],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_committed_configs_pass_scanner() -> None:
    result = _run(ROOT / ".mcp.json", ROOT / ".cursor" / "mcp.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_scanner_fails_on_static_authorization(tmp_path: Path) -> None:
    bad = tmp_path / "bad.mcp.json"
    bad.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "l9": {
                        "url": "https://runtime.example/v1/mcp",
                        "headers": {"Authorization": "Bearer leak-token-value"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    result = _run(bad)
    assert result.returncode != 0
    assert "FAIL" in result.stdout
