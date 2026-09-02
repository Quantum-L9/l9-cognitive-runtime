"""Strict parsing tests — malformed inputs must not succeed."""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_cognitive_runtime.models.errors import InvalidValueError
from l9_cognitive_runtime.parsing import (
    ParseErrorCode,
    StrictParseError,
    confined_input_file,
    load_json_mapping,
    load_yaml_file,
    load_yaml_mapping,
    require_known_kernels,
    require_non_empty_plan,
)


def test_malformed_yaml_fails() -> None:
    with pytest.raises(StrictParseError) as exc:
        load_yaml_mapping(":\n  - broken", source="bad.yaml")
    assert exc.value.code == ParseErrorCode.MALFORMED_YAML


def test_empty_yaml_fails() -> None:
    with pytest.raises(StrictParseError) as exc:
        load_yaml_mapping("   \n", source="empty.yaml")
    assert exc.value.code == ParseErrorCode.EMPTY_DOCUMENT


def test_malformed_json_fails() -> None:
    with pytest.raises(StrictParseError) as exc:
        load_json_mapping("{not json", source="bad.json")
    assert exc.value.code == ParseErrorCode.MALFORMED_JSON


def test_empty_plan_no_authority() -> None:
    with pytest.raises(StrictParseError) as exc:
        require_non_empty_plan({}, source="plan")
    assert exc.value.code == ParseErrorCode.EMPTY_PLAN


def test_unknown_kernel_never_substitutes() -> None:
    with pytest.raises(StrictParseError) as exc:
        require_known_kernels(["missing_kernel"], {"known"}, source="activation")
    assert exc.value.code == ParseErrorCode.UNKNOWN_KERNEL


def test_valid_yaml_loads() -> None:
    data = load_yaml_mapping("a: 1\nb:\n  - x\n")
    assert data["a"] == 1


def test_yaml_file_read_is_confined_to_recognized_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    config = repo / "config.yaml"
    config.write_text("safe: true\n", encoding="utf-8")

    assert load_yaml_file(config) == {"safe": True}


def test_confined_input_rejects_parent_escape_and_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    outside = tmp_path / "outside.yaml"
    outside.write_text("escaped: true\n", encoding="utf-8")

    with pytest.raises(InvalidValueError, match="escapes allow_root"):
        confined_input_file(outside, allow_root=repo)

    link = repo / "linked.yaml"
    link.symlink_to(outside)
    with pytest.raises(InvalidValueError, match="escapes allow_root"):
        confined_input_file(link, allow_root=repo)


def test_yaml_file_without_repository_or_pack_boundary_fails_closed(tmp_path: Path) -> None:
    orphan = tmp_path / "orphan.yaml"
    orphan.write_text("unsafe: true\n", encoding="utf-8")
    with pytest.raises(InvalidValueError, match="recognized repository or runtime pack"):
        load_yaml_file(orphan)
