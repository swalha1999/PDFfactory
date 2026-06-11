"""Render a crew-supplied DiagramSpec as a TikZ block diagram (R11).

The LLM only supplies labels and edge indices; all TikZ syntax is generated
here with escaped text, so the diagram stays compile-safe. Falls back to
the static pipeline diagram in elements.py when no usable spec exists.
"""

from __future__ import annotations

from agentscribe.services.crew.models import DiagramSpec
from agentscribe.services.latex.md_inline import escape_tex

NODES_PER_ROW = 3

HEADER = r"""\section{Block Diagram}
The diagram below shows a process described in this article.

\begin{figure}[ht!]
\centering
\begin{tikzpicture}[
    node distance=1.1cm and 1.2cm,
    block/.style={rectangle, rounded corners, draw, fill=blue!10,
                  minimum width=2.4cm, minimum height=1cm, align=center,
                  text width=2.6cm},
    arrow/.style={-{Stealth[length=3mm]}, thick}
]"""

FOOTER = r"""\end{tikzpicture}
\caption{%s}
\end{figure}
"""


def _node_position(index: int) -> str:
    """Grid placement: rows of three, first column anchors each new row."""
    if index == 0:
        return ""
    row, column = divmod(index, NODES_PER_ROW)
    if column == 0:
        return f", below=of n{index - NODES_PER_ROW}"
    return f", right=of n{index - 1}"


def render_diagram(spec: DiagramSpec) -> str:
    """TikZ source for a usable spec (caller checks spec.usable())."""
    lines = [HEADER]
    for index, label in enumerate(spec.nodes):
        text = escape_tex(label[:40])
        lines.append(rf"\node[block{_node_position(index)}] (n{index}) {{{text}}};")
    for source, target in spec.edges:
        lines.append(rf"\draw[arrow] (n{source}) -- (n{target});")
    lines.append(FOOTER % escape_tex(spec.caption[:120]))
    return "\n".join(lines)
