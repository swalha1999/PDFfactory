"""Validation context: everything the C1-C11 checks read, loaded once.

Deterministic parsing only (ADR-007) - pypdf for structure/links,
pdfplumber for text, plus the run directory's .tex/.log/.aux/.bib files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader

from agentscribe import constants


@dataclass
class ValidationContext:
    """Pre-extracted inputs shared by all envelope checks."""

    pdf_path: Path
    build_dir: Path
    page_count: int = 0
    page_texts: list[str] = field(default_factory=list)
    internal_link_count: int = 0
    tex: str = ""
    logs: str = ""
    final_log: str = ""  # last LaTeX pass only - earlier passes legitimately
    # contain undefined-citation warnings that bibtex later resolves
    aux: str = ""
    bib: str = ""
    manifest: list[dict[str, str]] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(self.page_texts)


def _count_internal_links(reader: PdfReader) -> int:
    count = 0
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            if obj.get("/Subtype") == "/Link":
                action = obj.get("/A")
                has_goto = action is not None and action.get_object().get("/S") == "/GoTo"
                if has_goto or obj.get("/Dest") is not None:
                    count += 1
    return count


def _read_all(build_dir: Path, pattern: str) -> str:
    parts = [
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(build_dir.glob(pattern))
    ]
    return "\n".join(parts)


def load_context(pdf_path: Path, build_dir: Path) -> ValidationContext:
    """Read the PDF and build artifacts once; checks stay pure functions."""
    ctx = ValidationContext(pdf_path=pdf_path, build_dir=build_dir)
    reader = PdfReader(str(pdf_path))
    ctx.page_count = len(reader.pages)
    ctx.internal_link_count = _count_internal_links(reader)
    with pdfplumber.open(str(pdf_path)) as pdf:
        ctx.page_texts = [page.extract_text() or "" for page in pdf.pages]
    tex_path = build_dir / constants.MAIN_TEX_NAME
    ctx.tex = tex_path.read_text(encoding="utf-8") if tex_path.is_file() else ""
    ctx.logs = _read_all(build_dir, "*.log")
    pass_logs = sorted(build_dir.glob("pass*.log"), key=lambda p: p.name)
    final = pass_logs[-1] if pass_logs else build_dir / "main.log"
    ctx.final_log = final.read_text(encoding="utf-8", errors="replace") if final.is_file() else ""
    ctx.aux = _read_all(build_dir, "*.aux")
    bib_path = build_dir / constants.REFERENCES_BIB_NAME
    ctx.bib = bib_path.read_text(encoding="utf-8") if bib_path.is_file() else ""
    manifest_path = build_dir / constants.FIGURE_MANIFEST_NAME
    if manifest_path.is_file():
        data: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
        ctx.manifest = list(data)
    return ctx
