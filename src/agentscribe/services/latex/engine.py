"""LaTeX engine: draft -> guaranteed-envelope main.tex + figures + bib (#22, #23).

Scans the draft for every graded element (table, formula, figure, BiDi
chapter, >=2 citations) and deterministically injects whatever is missing,
then writes all build inputs under the run directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from agentscribe import constants
from agentscribe.services.crew.models import MarkdownDraft
from agentscribe.services.latex import elements
from agentscribe.services.latex.bibliography import (
    bib_body,
    bib_preamble,
    build_bib,
    normalize_sources,
)
from agentscribe.services.latex.diagram import render_diagram
from agentscribe.services.latex.figures import generate_chart
from agentscribe.services.latex.md_inline import convert_inline
from agentscribe.services.latex.md_to_tex import contains_hebrew, convert_markdown_body
from agentscribe.services.latex.templates import assemble_document
from agentscribe.shared.config import Config
from agentscribe.shared.logging_setup import get_logger

TABLE_MARKER = re.compile(r"^\s*\|.+\|\s*$", re.M)
FORMULA_MARKER = re.compile(r"\$\$")
FIGURE_MARKER = re.compile(r"!\[FIGURE:", re.M)
CITE_MARKER = re.compile(r"\[@([A-Za-z0-9_:.-]+)\]")


class BuildArtifacts(BaseModel):
    """Build inputs/outputs under results/<run-id>/ (latex PRD §2.2)."""

    tex_path: Path
    bib_path: Path
    figure_paths: list[Path] = Field(default_factory=list)
    pdf_path: Path | None = None
    compiler_logs: list[str] = Field(default_factory=list)
    degraded_figure: bool = False
    figure_manifest: list[dict[str, str]] = Field(default_factory=list)


REFERENCES_HEADING = re.compile(r"^\s*(\d+[.)]?\s*)?(references|bibliography|sources)\s*$", re.I)


def ensure_elements(draft: MarkdownDraft, cite_keys: list[str]) -> str:
    """Return the full Markdown with every missing envelope element appended."""
    chapters = [c for c in draft.chapters if not REFERENCES_HEADING.match(c.heading)]
    # the real bibliography is generated from sources - an LLM-written
    # references chapter would duplicate it (and overflow with raw urls)
    markdown = "\n\n".join(f"## {c.heading}\n\n{c.body_markdown}" for c in chapters)
    if not TABLE_MARKER.search(markdown):
        markdown += "\n\n" + elements.DEFAULT_TABLE_MD
    if not FORMULA_MARKER.search(markdown):
        markdown += "\n\n" + elements.FANCY_FORMULA_MD
    if not FIGURE_MARKER.search(markdown):
        markdown += "\n\n" + elements.FIGURE_PLACEHOLDER_MD
    if not contains_hebrew(markdown):
        markdown += "\n\n" + elements.BIDI_CHAPTER_MD
    if len(set(CITE_MARKER.findall(markdown))) < 2:
        markdown += "\n\n" + elements.CITATION_SENTENCE_MD.format(
            key1=cite_keys[0], key2=cite_keys[1]
        )
    return markdown


class LatexEngine:
    """Builds all LaTeX inputs for a draft; compilation lives in compiler.py."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._log = get_logger(service="latex")

    def build(self, draft: MarkdownDraft, run_dir: Path, date: str) -> BuildArtifacts:
        """Write main.tex, references.bib and the sandbox-generated chart."""
        run_dir.mkdir(parents=True, exist_ok=True)
        sources = normalize_sources(draft.sources)
        keys = [s.cite_key for s in sources]
        markdown = ensure_elements(draft, keys)
        if draft.diagram is not None and draft.diagram.usable():
            diagram_tex = render_diagram(draft.diagram)
        else:
            diagram_tex = elements.TIKZ_DIAGRAM_TEX
        body_tex = convert_markdown_body(markdown) + "\n" + diagram_tex
        backend = self._config.bib_backend
        document = assemble_document(
            self._config,
            draft.title,
            date,
            body_tex,
            bib_body(backend),
            preamble_extra=bib_preamble(backend),
        )
        tex_path = run_dir / constants.MAIN_TEX_NAME
        tex_path.write_text(document, encoding="utf-8")
        bib_path = run_dir / constants.REFERENCES_BIB_NAME
        bib_path.write_text(build_bib(sources, year=date[:4]), encoding="utf-8")
        figure_path, degraded, sandbox_result = generate_chart(
            self._config, draft.title, run_dir, spec=draft.chart
        )
        manifest_path = run_dir / constants.FIGURE_MANIFEST_NAME
        manifest_path.write_text(json.dumps(sandbox_result.manifest, indent=2), encoding="utf-8")
        self._log.info(
            "latex_build_done",
            tex=str(tex_path),
            sources=len(sources),
            degraded_figure=degraded,
        )
        return BuildArtifacts(
            tex_path=tex_path,
            bib_path=bib_path,
            figure_paths=[figure_path],
            degraded_figure=degraded,
            figure_manifest=sandbox_result.manifest,
        )


def heading_to_tex(heading: str) -> str:
    """Expose inline conversion for report rendering elsewhere."""
    return convert_inline(heading)
