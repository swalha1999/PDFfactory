"""Project-wide constants and fixed defaults.

Centralised so no business value is hard-coded across modules (PRD §4.3).
Runtime-tunable values live in config/*.json; these are stable identifiers.
"""

from __future__ import annotations

from enum import Enum

# Config schema version; every versioned config file starts at this (PLAN §6).
CONFIG_VERSION = "1.00"

# Content-envelope defaults (PRD §4.1). Overridable via config/setup.json.
DEFAULT_LANGUAGE = "en"
BIDI_CHAPTER_LANGUAGE = "he"
TARGET_PAGES = 15


class Compiler(str, Enum):
    """Supported LaTeX compilers (PLAN ADR-003: LuaLaTeX default)."""

    LUALATEX = "lualatex"
    XELATEX = "xelatex"


class DocumentClass(str, Enum):
    """Supported LaTeX document classes (PRD_latex_compiler §2.3)."""

    ARTICLE = "article"
    BOOK = "book"
