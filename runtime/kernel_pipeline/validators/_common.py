#!/usr/bin/env python3
"""Shared helpers for L9 clean kernel-pack validators."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

STATUS_PASS = "passed"
STATUS_FAIL = "failed"


def pack_root_from_file(file: str) -> Path:
    return Path(file).resolve().parents[3]


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_kernel_identity(path: Path, root: Path) -> dict[str, Any]:
    text = read_text(path)
    data: Any = {}
    if path.suffix in {".yaml", ".yml"}:
        try:
            data = yaml.safe_load(text) or {}
        except Exception:
            # Some files may contain multiple yaml docs or comments before a doc marker.
            docs = [d for d in yaml.safe_load_all(text) if isinstance(d, dict)]
            data = docs[0] if docs else {}
    else:
        data = {}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                data["canonical_name"] = stripped[2:].strip()
                break

    return {
        "path": rel(path, root),
        "name": data.get("kernel_id") or data.get("name") or data.get("canonical_name") or path.stem,
        "status": str(data.get("status", "ACTIVE" if "runtime/kernels/" in rel(path, root) else "UNKNOWN")).upper(),
        "category": data.get("category") or data.get("artifact_type") or path.parent.name,
        "activation_order": data.get("activation_order"),
    }


def kernel_files(root: Path) -> list[Path]:
    base = root / "runtime" / "kernels"
    return sorted([p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in {".yaml", ".yml", ".md"}])


def emit(result: dict[str, Any], json_mode: bool) -> int:
    if json_mode:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['status'].upper()}: {result['validator']}")
        for item in result.get("findings", []):
            print(f"- {item}")
    return 0 if result["status"] == STATUS_PASS else 1


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--root", default=None, help="Pack root. Defaults to validator-relative pack root.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def resolve_root(default_file: str, supplied: str | None) -> Path:
    return Path(supplied).resolve() if supplied else pack_root_from_file(default_file)
