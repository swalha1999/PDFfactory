"""Typed contracts between pipeline stages (PRD_crew_pipeline §3.2).

The crew's final task returns a validated ``MarkdownDraft`` via CrewAI's
``output_pydantic`` - the SDK never parses free text (AI_STACK §3).
"""

from __future__ import annotations

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


class ChartSpec(BaseModel):
    """Content for the run's Python-generated chart (C7), drawn from the
    article itself; invalid/missing specs fall back to a deterministic chart."""

    title: str = ""
    x_label: str = "Category"
    y_label: str = "Value"
    labels: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)

    def usable(self) -> bool:
        return (
            2 <= len(self.labels) <= 10
            and len(self.labels) == len(self.values)
            and bool(self.title.strip())
        )


class MarkdownDraft(BaseModel):
    """The crew's product: an edited, structured draft ready for LaTeX."""

    title: str
    chapters: list[Chapter]
    required_elements: RequiredElements
    sources: list[Source] = Field(default_factory=list)
    chart: ChartSpec | None = None

    def to_markdown(self) -> str:
        """Render the full draft as one Markdown document."""
        parts = [f"# {self.title}"]
        for chapter in self.chapters:
            parts.append(f"\n## {chapter.heading}\n\n{chapter.body_markdown}")
        return "\n".join(parts) + "\n"
