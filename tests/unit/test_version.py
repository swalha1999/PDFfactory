"""Tests for shared/version.py - the startup compatibility check."""

from __future__ import annotations

import pytest

from agentscribe.shared.version import (
    CODE_VERSION,
    VersionMismatchError,
    check_compatibility,
    parse_version,
)


def test_parse_version_happy_path() -> None:
    assert parse_version("1.00") == (1, 0)
    assert parse_version("2.13") == (2, 13)


@pytest.mark.parametrize("bad", ["", "abc", "1", "1.2.3", None])
def test_parse_version_rejects_malformed(bad: str | None) -> None:
    with pytest.raises(VersionMismatchError):
        parse_version(bad)  # type: ignore[arg-type]


def test_check_compatibility_accepts_same_major() -> None:
    check_compatibility(CODE_VERSION)
    check_compatibility("1.99")  # minor drift tolerated


def test_check_compatibility_rejects_other_major() -> None:
    with pytest.raises(VersionMismatchError, match="setup.json"):
        check_compatibility("2.00", source="setup.json")
