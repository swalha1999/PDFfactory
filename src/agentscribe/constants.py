"""Project-wide constants and fixed defaults.

Centralised so no business value is hard-coded across modules (PRD §4.3).
Runtime-tunable values live in config/*.json; these are stable identifiers.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

SETUP_CONFIG = "setup.json"
RATE_LIMITS_CONFIG = "rate_limits.json"
LOGGING_CONFIG = "logging_config.json"
MODEL_PRICES_CONFIG = "model_prices.json"

# Config schema version; every versioned config file starts at this (PLAN §6).
CONFIG_VERSION = "1.00"

# Content-envelope defaults (PRD §4.1). Overridable via config/setup.json.
DEFAULT_LANGUAGE = "en"
BIDI_CHAPTER_LANGUAGE = "he"
TARGET_PAGES = 15

OUTPUT_PDF_NAME = "output.pdf"
DRAFT_MD_NAME = "draft.md"
MAIN_TEX_NAME = "main.tex"
REFERENCES_BIB_NAME = "references.bib"
FIGURE_SCRIPT_NAME = "chart.py"
FIGURE_IMAGE_NAME = "chart.png"
FIGURE_MANIFEST_NAME = "figure_manifest.json"
ENVELOPE_REPORT_JSON = "envelope_report.json"
ENVELOPE_REPORT_MD = "envelope_report.md"
COST_REPORT_JSON = "cost_report.json"
COST_REPORT_MD = "cost_report.md"
RUN_LOG_NAME = "run.jsonl"


class Compiler(StrEnum):
    """Supported LaTeX compilers (PLAN ADR-003: LuaLaTeX default)."""

    LUALATEX = "lualatex"
    XELATEX = "xelatex"


class DocumentClass(StrEnum):
    """Supported LaTeX document classes (PRD_latex_compiler §2.3)."""

    ARTICLE = "article"
    BOOK = "book"


class BibBackend(StrEnum):
    """Supported bibliography backends (biber preferred; bibtex fallback)."""

    BIBTEX = "bibtex"
    BIBER = "biber"


class Stage(StrEnum):
    """Pipeline stages, in execution order."""

    RESEARCH = "research"
    WRITE = "write"
    EDIT = "edit"
    LATEX = "latex"
    COMPILE = "compile"
    VALIDATE = "validate"


ENVELOPE_CHECK_IDS = [f"C{i}" for i in range(1, 12)]
