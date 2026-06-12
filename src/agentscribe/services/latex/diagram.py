"""Render a crew-supplied DiagramSpec as a clean TikZ flow diagram (R11).

Nodes are laid out as a snake pipeline (rows of three, alternating
direction) and connected sequentially with straight arrows; at most one
extra edge from the spec is drawn as a curved feedback arrow. The LLM only
supplies labels (and optionally that one feedback edge), so diagrams stay
simple and never turn into crossing-arrow spaghetti.
"""

from __future__ import annotations

from agentscribe.services.crew.models import DiagramSpec
from agentscribe.services.latex.md_inline import escape_tex

COLUMNS = 3
X_STEP, Y_STEP = 4.4, 2.4  # cm between node centers

HEADER = r"""\section{Block Diagram}
The diagram below shows a process described in this article.

\begin{figure}[ht!]
\centering
\begin{tikzpicture}[
    block/.style={rectangle, rounded corners, draw, fill=blue!10,
                  minimum width=3.2cm, minimum height=1.1cm, align=center,
                  text width=3.2cm},
    arrow/.style={-{Stealth[length=3mm]}, thick}
]"""

FOOTER = r"""\end{tikzpicture}
\caption{%s}
\end{figure}
"""


def _grid_position(index: int) -> tuple[float, float]:
    """Snake layout: rows of three, odd rows flow right-to-left."""
    row, column = divmod(index, COLUMNS)
    if row % 2 == 1:
        column = COLUMNS - 1 - column
    return column * X_STEP, -row * Y_STEP


def _feedback_edge(spec: DiagramSpec) -> tuple[int, int] | None:
    """The first non-sequential edge, if any - drawn curved, max one."""
    for source, target in spec.edges:
        if target != source + 1:
            return source, target
    return None


def render_diagram(spec: DiagramSpec) -> str:
    """TikZ source for a usable spec (caller checks spec.usable())."""
    lines = [HEADER]
    for index, label in enumerate(spec.nodes):
        x, y = _grid_position(index)
        text = escape_tex(label[:40])
        lines.append(rf"\node[block] (n{index}) at ({x:.1f}, {y:.1f}) {{{text}}};")
    for index in range(len(spec.nodes) - 1):  # the sequential pipeline
        lines.append(rf"\draw[arrow] (n{index}) -- (n{index + 1});")
    feedback = _feedback_edge(spec)
    if feedback is not None:
        source, target = feedback
        lines.append(rf"\draw[arrow, dashed] (n{source}) to[bend left=35] (n{target});")
    lines.append(FOOTER % escape_tex(spec.caption[:120]))
    return "\n".join(lines)
