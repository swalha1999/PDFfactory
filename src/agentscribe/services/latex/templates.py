"""LaTeX document scaffolding: preamble, cover sheet, TOC, headers (C2-C5).

All variable values (fonts, sizes, cover metadata) come from config -
nothing graded is hard-coded (latex PRD R1-R3).
"""

from __future__ import annotations

from agentscribe.services.latex.md_inline import escape_tex
from agentscribe.shared.config import Config

PREAMBLE_TEMPLATE = r"""\documentclass[{font_size}]{{{document_class}}}
\usepackage[a4paper,margin={margin_cm}cm]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage{{booktabs,tabularx}}
\usepackage{{tikz}}
\usetikzlibrary{{shapes.geometric,arrows.meta,positioning}}
\usepackage{{fancyhdr}}
\usepackage{{fontspec}}
\usepackage{{polyglossia}}
\setmainlanguage{{english}}
\setotherlanguage{{hebrew}}
\newfontfamily\hebrewfont[Script=Hebrew]{{{hebrew_font}}}
\usepackage{{microtype}}
\emergencystretch=3em
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{{hyperref}}

\pagestyle{{fancy}}
\fancyhf{{}}
\fancyhead[L]{{\small {short_title}}}
\fancyhead[R]{{\small \thepage}}
\fancyfoot[C]{{\small {course}}}
\setlength{{\headheight}}{{15pt}}
"""

COVER_TEMPLATE = r"""\begin{{titlepage}}
\centering
\vspace*{{2cm}}
{{\Huge\bfseries {title}\par}}
\vspace{{2cm}}
{{\Large {author}\par}}
\vspace{{1cm}}
{{\large Course: {course}\par}}
{{\large Lecturer: {lecturer}\par}}
\vfill
{{\large {date}\par}}
\end{{titlepage}}
"""


def render_preamble(config: Config, title: str) -> str:
    """Document class, packages, BiDi setup, fancyhdr headers/footers (C5)."""
    latex_cfg = config.latex
    short = escape_tex(title if len(title) <= 60 else title[:57] + "...")
    return PREAMBLE_TEMPLATE.format(
        font_size=latex_cfg["font_size"],
        document_class=config.document_class,
        margin_cm=latex_cfg["margin_cm"],
        hebrew_font=latex_cfg["hebrew_font"],
        short_title=short,
        course=escape_tex(config.cover["course"]),
    )


def render_cover(config: Config, title: str, date: str) -> str:
    """Cover sheet: topic, author, date, course, lecturer (C2)."""
    cover = config.cover
    return COVER_TEMPLATE.format(
        title=escape_tex(title),
        author=escape_tex(cover["author"]),
        course=escape_tex(cover["course"]),
        lecturer=escape_tex(cover["lecturer"]),
        date=escape_tex(date),
    )


def assemble_document(
    config: Config,
    title: str,
    date: str,
    body_tex: str,
    bibliography_tex: str,
    preamble_extra: str = "",
) -> str:
    """Full main.tex: preamble + cover + TOC + body + bibliography (C2-C5)."""
    return "\n".join(
        [
            render_preamble(config, title),
            preamble_extra,
            r"\begin{document}",
            render_cover(config, title, date),
            r"\tableofcontents",
            r"\newpage",
            "",
            body_tex,
            "",
            bibliography_tex,
            r"\end{document}",
            "",
        ]
    )
