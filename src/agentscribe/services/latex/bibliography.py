"""Bibliography generation: references.bib + backend commands (C11, #24).

Sources come from the crew's research; when fewer than two usable sources
exist, committed defaults guarantee the envelope still has linked,
clickable citations.
"""

from __future__ import annotations

import re

from agentscribe import constants
from agentscribe.services.crew.models import Source
from agentscribe.services.latex.md_inline import escape_tex

DEFAULT_SOURCES = [
    Source(title="CrewAI Documentation", url="https://docs.crewai.com", cite_key="crewai2026docs"),
    Source(
        title="ISO/IEC 25010 - Systems and software Quality Requirements and Evaluation",
        url="https://www.iso.org/standard/35733.html",
        cite_key="iso25010",
    ),
]

BIB_FILE_STEM = constants.REFERENCES_BIB_NAME.removesuffix(".bib")


def normalize_sources(sources: list[Source]) -> list[Source]:
    """Dedupe by cite_key, sanitize keys, and top up with defaults (>=2)."""
    seen: dict[str, Source] = {}
    for source in sources:
        key = re.sub(r"[^A-Za-z0-9_:.-]", "", source.cite_key)
        if key and key not in seen:
            seen[key] = Source(title=source.title, url=source.url, cite_key=key)
    for default in DEFAULT_SOURCES:
        if len(seen) >= 2:
            break
        seen.setdefault(default.cite_key, default)
    return list(seen.values())


def build_bib(sources: list[Source], year: str) -> str:
    """Render references.bib content (@misc entries with urls)."""
    entries = []
    for source in sources:
        title = escape_tex(source.title)
        entries.append(
            f"@misc{{{source.cite_key},\n"
            f"  title = {{{title}}},\n"
            f"  howpublished = {{\\url{{{source.url}}}}},\n"
            f"  year = {{{year}}},\n"
            f"  note = {{Accessed {year}}}\n"
            f"}}"
        )
    return "\n\n".join(entries) + "\n"


def bib_preamble(backend: constants.BibBackend) -> str:
    """Preamble lines the chosen backend needs (biblatex for biber)."""
    if backend is constants.BibBackend.BIBER:
        return (
            "\\usepackage[backend=biber,style=numeric]{biblatex}\n"
            f"\\addbibresource{{{constants.REFERENCES_BIB_NAME}}}\n"
        )
    return ""


def bib_body(backend: constants.BibBackend) -> str:
    """Body commands that render the bibliography with hyperref links."""
    if backend is constants.BibBackend.BIBER:
        return "\\printbibliography[heading=bibintoc]\n"
    return (
        "\\clearpage\n"
        "\\addcontentsline{toc}{section}{References}\n"
        "\\bibliographystyle{plain}\n"
        f"\\bibliography{{{BIB_FILE_STEM}}}\n"
    )
