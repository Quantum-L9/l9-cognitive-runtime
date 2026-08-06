#!/usr/bin/env python3
"""Fail closed if MCP client configs contain static credentials (L9CR-MCP-013)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FORBIDDEN_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "api-key",
        "access_token",
        "accesstoken",
        "refresh_token",
        "client_secret",
        "clientsecret",
        "password",
        "token",
        "headers",
        "pat",
        "bearer",
    }
)

# Values that look like embedded secrets (not hostnames/URLs).
SECRET_VALUE = re.compile(
    r"(?i)(\bbearer\s+[A-Za-z0-9\-._~+/]+=*|sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})"
)


def _walk(obj: object, path: str, findings: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            child = f"{path}.{key}" if path else str(key)
            if key_l in FORBIDDEN_KEYS:
                findings.append(f"{child}: forbidden credential key")
            _walk(value, child, findings)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk(item, f"{path}[{i}]", findings)
    elif isinstance(obj, str) and SECRET_VALUE.search(obj):
        findings.append(f"{path}: value matches secret pattern")


def scan_file(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    findings: list[str] = []
    _walk(data, "", findings)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    for path in args.paths:
        findings = scan_file(path)
        if findings:
            failed = 1
            print(f"FAIL {path}")
            for item in findings:
                print(f"  - {item}")
        else:
            print(f"PASS {path}")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
