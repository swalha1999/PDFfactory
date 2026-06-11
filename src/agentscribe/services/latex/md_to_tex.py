"""Deterministic Markdown -> LaTeX body conversion (latex PRD; ADR-002).

No LLM involvement: headings, emphasis, tables, math blocks, figures,
citations, lists and Hebrew runs are converted by rules so the result is
testable. Hebrew runs are wrapped for polyglossia BiDi (C10).
"""

from __future__ import annotations

import re

from agentscribe.services.latex import md_inline
from agentscribe.services.latex.md_inline import convert_inline

FIGURE_RE = re.compile(r"^!\[FIGURE:\s*(?P<desc>[^\]]+)\]\((?P<file>[^)]+)\)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_RULE_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


def _table_cells(line: str) -> list[str]:
    match = TABLE_ROW_RE.match(line)
    inner = match.group(1) if match else line.strip().strip("|")
    return [convert_inline(cell.strip()) for cell in inner.split("|")]


def _emit_table(rows: list[str]) -> list[str]:
    header = _table_cells(rows[0])
    body = [r for r in rows[1:] if not TABLE_RULE_RE.match(r)]
    columns = len(header)
    spec = "X" * columns  # tabularx X columns share \textwidth - no overflow (C8)
    out = [r"\begin{table}[ht!]", r"\centering", rf"\begin{{tabularx}}{{\textwidth}}{{{spec}}}"]
    out += [r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    for row in body:
        cells = _table_cells(row)
        cells += [""] * (columns - len(cells))
        out.append(" & ".join(cells[:columns]) + r" \\")
    out += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
    return out


def _emit_figure(desc: str, filename: str) -> list[str]:
    caption = convert_inline(desc.strip())
    return [
        r"\begin{figure}[ht!]",
        r"\centering",
        rf"\includegraphics[width=0.85\textwidth]{{{filename}}}",
        rf"\caption{{{caption}}}",
        r"\end{figure}",
    ]


def _flush_list(out: list[str], kind: str | None) -> None:
    if kind:
        out.append(rf"\end{{{kind}}}")


def convert_markdown_body(markdown: str) -> str:
    """Convert a chapter body (no # title) to a LaTeX fragment."""
    out: list[str] = []
    lines = markdown.splitlines()
    i, in_list = 0, None
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("$$"):  # display math block -> equation (C9)
            block, i = _collect_math(lines, i)
            _flush_list(out, in_list)
            in_list = None
            out += [r"\begin{equation}", block, r"\end{equation}"]
            continue
        if TABLE_ROW_RE.match(line) and i + 1 < len(lines) and TABLE_RULE_RE.match(lines[i + 1]):
            rows = []
            while i < len(lines) and TABLE_ROW_RE.match(lines[i]):
                rows.append(lines[i])
                i += 1
            _flush_list(out, in_list)
            in_list = None
            out += _emit_table(rows)
            continue
        figure = FIGURE_RE.match(stripped)
        if figure:
            _flush_list(out, in_list)
            in_list = None
            out += _emit_figure(figure["desc"], figure["file"])
        elif stripped.startswith("#"):
            _flush_list(out, in_list)
            in_list = None
            level = len(stripped) - len(stripped.lstrip("#"))
            command = {1: "section", 2: "section", 3: "subsection"}.get(level, "subsubsection")
            heading = stripped.lstrip("#").strip()
            # LaTeX numbers sections itself - drop LLM-written "7." / "Chapter 7:"
            heading = re.sub(r"^(chapter\s+)?\d+(\.\d+)*[.):]?\s+", "", heading, flags=re.I)
            out.append(rf"\{command}{{{convert_inline(heading)}}}")
        elif re.match(r"^\s*[-*]\s+", line):
            if in_list != "itemize":
                _flush_list(out, in_list)
                out.append(r"\begin{itemize}")
                in_list = "itemize"
            out.append(r"\item " + convert_inline(re.sub(r"^\s*[-*]\s+", "", line)))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            if in_list != "enumerate":
                _flush_list(out, in_list)
                out.append(r"\begin{enumerate}")
                in_list = "enumerate"
            out.append(r"\item " + convert_inline(re.sub(r"^\s*\d+[.)]\s+", "", line)))
        elif stripped:
            _flush_list(out, in_list)
            in_list = None
            out.append(convert_inline(stripped))
        else:
            _flush_list(out, in_list)
            in_list = None
            out.append("")
        i += 1
    _flush_list(out, in_list)
    return "\n".join(out).strip() + "\n"


def _collect_math(lines: list[str], i: int) -> tuple[str, int]:
    first = lines[i].strip()
    if first.startswith("$$") and first.endswith("$$") and len(first) > 4:
        return first.strip("$").strip(), i + 1
    block: list[str] = []
    i += 1
    while i < len(lines) and not lines[i].strip().startswith("$$"):
        block.append(lines[i])
        i += 1
    return "\n".join(block).strip(), i + 1


def contains_hebrew(text: str) -> bool:
    """True when the text contains Hebrew codepoints (C10 detection)."""
    return bool(md_inline.HEBREW_RUN.search(text))
