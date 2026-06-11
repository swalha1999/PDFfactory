"""Tests for the envelope checks (EV-2..EV-6) and the report artifact."""

from __future__ import annotations

from pathlib import Path

from agentscribe.services.validate import checks
from agentscribe.services.validate.context import ValidationContext
from agentscribe.services.validate.report import CheckOutcome, EnvelopeReport

GOOD_TEX = r"""
\tableofcontents
\pagestyle{fancy}
\section{One}\section{Two}\section{Three}
\begin{tabularx}{\textwidth}{XX} a & b \\ \end{tabularx}
\begin{equation} E = mc^2 \end{equation}
\texthebrew{שלום}
\includegraphics{chart.png}
\cite{k1} \cite{k2}
"""


def ctx(**overrides: object) -> ValidationContext:
    base = ValidationContext(
        pdf_path=Path("x.pdf"),
        build_dir=Path("."),
        page_count=15,
        page_texts=["Contents Title Author", "body שלום and english text"],
        internal_link_count=12,
        tex=GOOD_TEX,
        logs="Package: fancyhdr",
        aux="",
        bib="@misc{k1,\n}\n@misc{k2,\n}",
        manifest=[{"file": "chart.png", "sha256": "x", "source": "sandbox"}],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_c1_page_count_tolerance() -> None:
    assert checks.c1_page_count(ctx(page_count=12), 15, 3).ok
    assert not checks.c1_page_count(ctx(page_count=4), 15, 3).ok


def test_c3_c4_c5_structure_checks() -> None:
    assert checks.c3_toc(ctx()).ok
    assert not checks.c3_toc(ctx(internal_link_count=0)).ok
    assert checks.c4_chapters(ctx()).ok
    assert not checks.c4_chapters(ctx(tex=r"\section{Only}")).ok
    assert checks.c5_headers(ctx()).ok
    assert not checks.c5_headers(ctx(logs="")).ok


def test_c6_image_targets_must_exist(tmp_path: Path) -> None:
    (tmp_path / "chart.png").write_bytes(b"png")
    assert checks.c6_image(ctx(build_dir=tmp_path)).ok
    assert not checks.c6_image(ctx(build_dir=tmp_path / "empty")).ok


def test_c7_requires_sandbox_provenance(tmp_path: Path) -> None:
    (tmp_path / "chart.png").write_bytes(b"png")
    assert checks.c7_python_graph(ctx(build_dir=tmp_path), "chart.png").ok
    degraded = checks.c7_python_graph(ctx(build_dir=tmp_path, manifest=[]), "chart.png")
    assert not degraded.ok
    assert "degraded" in degraded.detail


def test_ev4_overfull_table_flagged() -> None:
    logs = "Package: fancyhdr\nOverfull \\hbox (25.31pt too wide) in paragraph"
    result = checks.c8_table(ctx(logs=logs), threshold_pt=10)
    assert not result.ok
    assert result.remediation == "table_overflow"
    assert checks.c8_table(ctx(), threshold_pt=10).ok  # small overfulls tolerated


def test_ev3_flat_formula_detection() -> None:
    no_math = ctx(tex=r"\section{A}\section{B}\section{C} prose E = mc^2 here")
    result = checks.c9_math(no_math)
    assert not result.ok
    assert result.remediation == "flat_formula"
    assert checks.c9_math(ctx()).ok


def test_ev5_missing_hebrew_fails_bidi() -> None:
    assert checks.c10_bidi(ctx()).ok
    assert not checks.c10_bidi(ctx(page_texts=["english only"])).ok
    assert not checks.c10_bidi(ctx(tex="no hebrew env")).ok


def test_ev2_undefined_citation_maps_to_missing_pass() -> None:
    logs = "Package: fancyhdr\nLaTeX Warning: Citation `k1' on page 3 undefined"
    result = checks.c11_bibliography(ctx(logs=logs))
    assert not result.ok
    assert result.remediation == "missing_pass"
    assert checks.c11_bibliography(ctx()).ok


def test_c11_key_missing_from_bib() -> None:
    result = checks.c11_bibliography(ctx(bib="@misc{k1,\n}"))
    assert not result.ok
    assert "k2" in result.detail


def test_c2_cover_fields() -> None:
    cover = {"author": "Author", "course": "Course", "lecturer": "Lect"}
    good = ctx(page_texts=["Title Author Course Lect", ""])
    assert checks.c2_cover(good, cover, "Title X").ok
    assert not checks.c2_cover(ctx(page_texts=["empty", ""]), cover, "Title X").ok


def test_report_writes_json_and_markdown(tmp_path: Path) -> None:
    report = EnvelopeReport(
        checks={"C1_page_count": CheckOutcome(ok=False, detail="4 pages", remediation=None)},
        all_pass=False,
        remediations=["missing_pass"],
    )
    report.write(tmp_path)
    assert (tmp_path / "envelope_report.json").is_file()
    md = (tmp_path / "envelope_report.md").read_text()
    assert "FAILURES PRESENT" in md
    assert "C1_page_count" in md
    assert "missing_pass" in md
