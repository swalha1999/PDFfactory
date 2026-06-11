"""Tests for templates.py and bibliography.py (C2-C5, C11)."""

from __future__ import annotations

from agentscribe import constants
from agentscribe.services.crew.models import Source
from agentscribe.services.latex.bibliography import (
    bib_body,
    bib_preamble,
    build_bib,
    normalize_sources,
)
from agentscribe.services.latex.templates import (
    assemble_document,
    render_cover,
    render_preamble,
)
from agentscribe.shared.config import Config


def test_preamble_has_envelope_packages() -> None:
    tex = render_preamble(Config(), "My Topic & More")
    for needle in (
        r"\usepackage{fancyhdr}",
        r"\usepackage{polyglossia}",
        r"\setotherlanguage{hebrew}",
        r"\newfontfamily\hebrewfont",
        r"\usepackage{tikz}",
        r"\usepackage{booktabs,tabularx}",
        "colorlinks=true",
        r"\fancyhead[R]{\small \thepage}",
    ):
        assert needle in tex, needle
    assert r"My Topic \& More" in tex  # header title escaped


def test_cover_contains_all_required_fields() -> None:
    config = Config()
    tex = render_cover(config, "Agentic AI", "2026-06-11")
    assert "Agentic AI" in tex
    assert config.cover["author"] in tex
    assert config.cover["course"] in tex
    assert config.cover["lecturer"] in tex
    assert "2026-06-11" in tex


def test_assemble_document_order() -> None:
    tex = assemble_document(Config(), "T", "2026", "BODY", "BIBLIO", preamble_extra="EXTRA")
    assert tex.index("EXTRA") < tex.index(r"\begin{document}")
    assert tex.index(r"\tableofcontents") < tex.index("BODY") < tex.index("BIBLIO")
    assert tex.rstrip().endswith(r"\end{document}")


def test_normalize_sources_dedupes_and_tops_up() -> None:
    sources = [
        Source(title="A", url="https://a", cite_key="dup"),
        Source(title="B", url="https://b", cite_key="dup"),
        Source(title="C", url="https://c", cite_key="bad key!"),
    ]
    normalized = normalize_sources(sources)
    keys = [s.cite_key for s in normalized]
    assert "dup" in keys
    assert "badkey" in keys
    assert len(keys) == len(set(keys))
    assert len(keys) >= 2
    assert len(normalize_sources([])) == 2  # defaults guarantee C11


def test_build_bib_renders_misc_entries() -> None:
    bib = build_bib([Source(title="T_1", url="https://x", cite_key="k1")], year="2026")
    assert "@misc{k1," in bib
    assert r"\url{https://x}" in bib
    assert "T\\_1" in bib
    assert "year = {2026}" in bib


def test_bib_backend_commands() -> None:
    assert "bibliographystyle" in bib_body(constants.BibBackend.BIBTEX)
    assert bib_preamble(constants.BibBackend.BIBTEX) == ""
    assert "biblatex" in bib_preamble(constants.BibBackend.BIBER)
    assert "printbibliography" in bib_body(constants.BibBackend.BIBER)
