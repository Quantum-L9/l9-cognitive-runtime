"""Immutable runtime pack loading, manifest verification, and provenance."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from l9_cognitive_runtime.models.errors import InvalidValueError


@dataclass(frozen=True)
class PackProvenance:
    pack_ref: str
    root: Path
    manifest_digest: str
    file_digests: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_ref": self.pack_ref,
            "root": str(self.root),
            "manifest_digest": self.manifest_digest,
            "file_digests": dict(self.file_digests),
        }


@dataclass(frozen=True)
class RuntimePack:
    """Immutable view of a verified pack root."""

    provenance: PackProvenance
    manifest: Mapping[str, Any]

    def resolve(self, relative: str) -> Path:
        """Resolve a relative path within the pack; reject traversal escapes."""
        if not relative or relative.startswith(("/", "\\")):
            raise InvalidValueError("absolute pack paths are forbidden", path=relative)
        candidate = (self.provenance.root / relative).resolve()
        root = self.provenance.root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise InvalidValueError("path escapes pack root", path=relative) from exc
        if not candidate.exists():
            raise InvalidValueError("pack path missing", path=relative)
        return candidate


class PackLoader:
    """Load an explicit pack_ref, verify MANIFEST.json digests, return immutable pack."""

    def load(self, pack_ref: str | Path) -> RuntimePack:
        if pack_ref is None or str(pack_ref).strip() == "":
            raise InvalidValueError("explicit pack_ref required", path="pack_ref")
        root = Path(pack_ref).expanduser().resolve()
        if not root.is_dir():
            raise InvalidValueError("pack_ref is not a directory", path=str(root))
        manifest_path = root / "MANIFEST.json"
        if not manifest_path.is_file():
            raise InvalidValueError("missing MANIFEST.json", path=str(manifest_path))
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InvalidValueError("manifest is not valid JSON", path=str(manifest_path)) from exc
        if not isinstance(manifest, dict):
            raise InvalidValueError("manifest root must be an object", path=str(manifest_path))
        files = manifest.get("files")
        if not isinstance(files, list):
            raise InvalidValueError("manifest.files must be a list", path="files")

        digests: dict[str, str] = {}
        for entry in files:
            if not isinstance(entry, dict):
                raise InvalidValueError("manifest file entry must be object", path="files")
            rel = entry.get("path")
            expected = entry.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected, str):
                raise InvalidValueError("manifest entry requires path+sha256", path="files")
            # Skip self-hash of MANIFEST.json if present — verify content files.
            if rel in {"MANIFEST.json"}:
                continue
            target = self._safe_join(root, rel)
            if not target.is_file():
                raise InvalidValueError("manifest lists missing file", path=rel)
            actual = _sha256_file(target)
            if actual != expected.lower() and actual != expected:
                raise InvalidValueError(
                    "manifest hash mismatch (tamper detected)",
                    path=rel,
                    details={"expected": expected, "actual": actual},
                )
            digests[rel] = actual

        manifest_digest = _sha256_file(manifest_path)
        provenance = PackProvenance(
            pack_ref=str(root),
            root=root,
            manifest_digest=manifest_digest,
            file_digests=digests,
        )
        return RuntimePack(provenance=provenance, manifest=manifest)

    @staticmethod
    def _safe_join(root: Path, relative: str) -> Path:
        if relative.startswith(("/", "\\")) or ".." in Path(relative).parts:
            raise InvalidValueError("path escapes pack root", path=relative)
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise InvalidValueError("path escapes pack root", path=relative) from exc
        return candidate


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
