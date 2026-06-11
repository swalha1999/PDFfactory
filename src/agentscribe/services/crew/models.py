"""Typed contracts between pipeline stages (PRD_crew_pipeline §3.2).

The crew's final task returns a validated ``MarkdownDraft`` via CrewAI's
``output_pydantic`` - the SDK never parses free text (AI_STACK §3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    """One research source; cite_key links draft citations to references.bib."""

    title: str
    url: str
    cite_key: str


class Chapter(BaseModel):
    """One chapter of the draft, heading plus Markdown body."""

    heading: str
    body_markdown: str


class RequiredElements(BaseModel):
    """Envelope-element markers the editor must guarantee (R4, C6-C11)."""

    table: bool = False
    formula: bool = False
    figure: bool = False
    bidi_section: bool = False
    citations: list[str] = Field(default_factory=list)

    def all_present(self) -> bool:
        return (
            self.table
            and self.formula
            and self.figure
            and self.bidi_section
            and len(self.citations) >= 2
        )


ChartKind = Literal["bar", "barh", "line", "pie"]


class ChartSpec(BaseModel):
    """Content for the run's Python-generated chart (C7), drawn from the
    article itself; invalid/missing specs fall back to a deterministic chart."""

    kind: ChartKind = "bar"
    title: str = ""
    x_label: str = "Category"
    y_label: str = "Value"
    labels: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)

    def usable(self) -> bool:
        if self.kind == "pie" and any(v <= 0 for v in self.values):
            return False
        return (
            2 <= len(self.labels) <= 10
            and len(self.labels) == len(self.values)
            and bool(self.title.strip())
        )


class DiagramSpec(BaseModel):
    """Block-diagram content (TikZ) drawn from the article: short node labels
    in flow order plus directed edges as [from_index, to_index] pairs."""

    caption: str = ""
    nodes: list[str] = Field(default_factory=list)
    edges: list[tuple[int, int]] = Field(default_factory=list)

    def usable(self) -> bool:
        n = len(self.nodes)
        return (
            3 <= n <= 8
            and bool(self.caption.strip())
            and len(self.edges) >= 2
            and all(0 <= a < n and 0 <= b < n and a != b for a, b in self.edges)
        )


class MarkdownDraft(BaseModel):
    """The crew's product: an edited, structured draft ready for LaTeX."""

    title: str
    chapters: list[Chapter]
    required_elements: RequiredElements
    sources: list[Source] = Field(default_factory=list)
    chart: ChartSpec | None = None
    charts: list[ChartSpec] = Field(default_factory=list)
    diagram: DiagramSpec | None = None

    def usable_charts(self) -> list[ChartSpec]:
        """All usable chart specs, primary first, deduped, capped at three."""
        candidates = ([self.chart] if self.chart else []) + list(self.charts)
        unique: list[ChartSpec] = []
        for spec in candidates:
            if spec.usable() and all(spec.title != seen.title for seen in unique):
                unique.append(spec)
        return unique[:3]

    def to_markdown(self) -> str:
        """Render the full draft as one Markdown document."""
        parts = [f"# {self.title}"]
        for chapter in self.chapters:
            parts.append(f"\n## {chapter.heading}\n\n{chapter.body_markdown}")
        return "\n".join(parts) + "\n"
