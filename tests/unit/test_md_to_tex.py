"""Tests for the deterministic Markdown -> LaTeX conversion (#19)."""

from __future__ import annotations

from agentscribe.services.latex.md_inline import convert_inline, escape_tex
from agentscribe.services.latex.md_to_tex import contains_hebrew, convert_markdown_body


def test_escape_tex_specials() -> None:
    assert escape_tex("50% & #1_x") == r"50\% \& \#1\_x"
    assert escape_tex("a$b") == r"a\$b"


def test_inline_bold_italic_code() -> None:
    assert convert_inline("**bold** and *it* and `code_x`") == (
        r"\textbf{bold} and \emph{it} and \texttt{code\_x}"
    )


def test_inline_citation_and_link_survive_escaping() -> None:
    assert convert_inline("see [@smith_2024] now") == r"see \cite{smith_2024} now"
    assert (
        convert_inline("[CrewAI docs](https://docs.crewai.com/a_b)")
        == r"\href{https://docs.crewai.com/a_b}{CrewAI docs}"
    )


def test_inline_math_preserved() -> None:
    assert convert_inline("energy $E = mc^2$ here") == r"energy $E = mc^2$ here"


def test_hebrew_runs_wrapped_for_bidi() -> None:
    out = convert_inline("The word שלום עולם means hello")
    assert r"\texthebrew{שלום עולם}" in out
    assert contains_hebrew("שלום")
    assert not contains_hebrew("hello")


def test_headings_map_to_sections() -> None:
    tex = convert_markdown_body("## Chapter\n\n### Sub\n\ntext")
    assert r"\section{Chapter}" in tex
    assert r"\subsection{Sub}" in tex


def test_display_math_becomes_equation() -> None:
    tex = convert_markdown_body("$$\nE = mc^2\n$$")
    assert r"\begin{equation}" in tex
    assert "E = mc^2" in tex
    one_line = convert_markdown_body("$$E = mc^2$$")
    assert r"\begin{equation}" in one_line


def test_table_becomes_tabularx_within_textwidth() -> None:
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    tex = convert_markdown_body(md)
    assert r"\begin{tabularx}{\textwidth}" in tex
    assert tex.count(r">{\raggedright\arraybackslash}X") == 2
    assert r"\toprule" in tex
    assert r"1 & 2 \\" in tex
    assert tex.count(r"\\") >= 3


def test_figure_placeholder_becomes_figure_env() -> None:
    tex = convert_markdown_body("![FIGURE: Growth of agents](chart.png)")
    assert r"\includegraphics[width=0.85\textwidth]{chart.png}" in tex
    assert r"\caption{Growth of agents}" in tex


def test_lists_convert_and_close() -> None:
    tex = convert_markdown_body("- one\n- two\n\ntext\n\n1. a\n2. b")
    assert tex.count(r"\begin{itemize}") == 1
    assert tex.count(r"\end{itemize}") == 1
    assert r"\item one" in tex
    assert r"\begin{enumerate}" in tex
    assert r"\end{enumerate}" in tex


def test_plain_paragraphs_escaped() -> None:
    tex = convert_markdown_body("AT&T owns 100% of it")
    assert r"AT\&T owns 100\% of it" in tex


def test_currency_amounts_are_not_math() -> None:
    text = "revenue reached $1.2 billion this year while Claude hit $3 billion ARR"
    out = convert_inline(text)
    assert out == (
        r"revenue reached \$1.2 billion this year while Claude hit \$3 billion ARR"
    )  # fully escaped prose, no math span
    # legit short math still protected
    assert convert_inline("energy $E = mc^2$ here") == r"energy $E = mc^2$ here"
    # a single dollar sign is plain prose
    assert convert_inline("it costs $5 today") == r"it costs \$5 today"
