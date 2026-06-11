"""Inline Markdown -> LaTeX conversion: escaping, emphasis, cites, Hebrew.

Protected spans (inline code, inline math, citations, links) are lifted out
before TeX escaping, then restored, so escaping never corrupts them.
"""

from __future__ import annotations

import re

TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "$": r"\$",
}
HEBREW_RUN = re.compile(r"[֐-׿][֐-׿\s,.:;!?'\"-]*[֐-׿]|[֐-׿]")
CODE_RE = re.compile(r"`([^`]+)`")
MATH_RE = re.compile(r"\$([^$]+)\$")
CITE_RE = re.compile(r"\[@([A-Za-z0-9_:.-]+)\]")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"\*([^*]+)\*")


def escape_tex(text: str) -> str:
    """Escape TeX special characters in plain prose."""
    return "".join(TEX_ESCAPES.get(ch, ch) for ch in text)


def convert_inline(text: str) -> str:
    """Convert one line of inline Markdown to LaTeX."""
    protected: list[str] = []

    def protect(replacement: str) -> str:
        protected.append(replacement)
        return f"\x00{len(protected) - 1}\x00"

    text = CODE_RE.sub(lambda m: protect(rf"\texttt{{{escape_tex(m.group(1))}}}"), text)
    text = LINK_RE.sub(
        lambda m: protect(rf"\href{{{m.group(2)}}}{{{escape_tex(m.group(1))}}}"), text
    )
    text = CITE_RE.sub(lambda m: protect(rf"\cite{{{m.group(1)}}}"), text)
    text = MATH_RE.sub(lambda m: protect(f"${m.group(1)}$"), text)
    text = escape_tex(text)
    text = BOLD_RE.sub(r"\\textbf{\1}", text)
    text = ITALIC_RE.sub(r"\\emph{\1}", text)
    text = HEBREW_RUN.sub(lambda m: rf"\texthebrew{{{m.group(0)}}}", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)
