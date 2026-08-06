"""Strict parsing tests — malformed inputs must not succeed."""

from __future__ import annotations

import pytest

from l9_cognitive_runtime.parsing import (
    ParseErrorCode,
    StrictParseError,
    load_json_mapping,
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
