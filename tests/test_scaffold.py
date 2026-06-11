"""Smoke tests for the package scaffold (docs/TODO.md T1.2)."""

from __future__ import annotations

import agentscribe
from agentscribe.constants import (
    CONFIG_VERSION,
    TARGET_PAGES,
    Compiler,
    DocumentClass,
)


def test_version_is_set() -> None:
    assert agentscribe.__version__ == "0.1.0"


def test_config_version_starts_at_one() -> None:
    assert CONFIG_VERSION == "1.00"


def test_default_target_pages() -> None:
    assert TARGET_PAGES == 15


def test_compiler_default_is_lualatex() -> None:
    assert Compiler.LUALATEX.value == "lualatex"
    assert Compiler.XELATEX.value == "xelatex"


def test_document_classes() -> None:
    assert {c.value for c in DocumentClass} == {"article", "book"}
