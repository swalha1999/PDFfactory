"""LC-1 integration smoke test: bare draft -> real multi-pass compile -> PDF.

Skipped automatically where no LaTeX distribution is installed (e.g. CI);
run locally to prove the full envelope toolchain works end to end.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agentscribe.services.crew.models import Chapter, MarkdownDraft, RequiredElements
from agentscribe.services.latex.compiler import compile_pdf
from agentscribe.services.latex.engine import LatexEngine
from agentscribe.shared.config import Config

needs_latex = pytest.mark.skipif(
    shutil.which("lualatex") is None or shutil.which("bibtex") is None,
    reason="LaTeX toolchain not installed",
)


@needs_latex
def test_lc1_bare_draft_compiles_to_pdf(tmp_path: Path) -> None:
    config = Config()
    draft = MarkdownDraft(
        title="Integration Smoke Topic",
        chapters=[
            Chapter(
                heading="Introduction",
                body_markdown="A short paragraph with a citation [@crewai2026docs].",
            )
        ],
        required_elements=RequiredElements(),
    )
    artifacts = LatexEngine(config).build(draft, tmp_path, "2026-06-11")
    assert artifacts.tex_path.is_file()
    pdf_path, logs = compile_pdf(config, tmp_path)
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 10_000
    assert len(logs) == 5  # 4 latex passes + bibtex
