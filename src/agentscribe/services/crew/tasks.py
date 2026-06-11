"""Task definitions with strict context chaining (crew PRD R3-R4).

Research -> Write -> Edit -> LaTeX-prep; each task receives its predecessor
via ``context=[...]`` (no manual prompt stitching). The final task returns a
validated ``MarkdownDraft`` through ``output_pydantic``.
"""

from __future__ import annotations

from crewai import Task

from agentscribe.services.crew.agents import AgentMap
from agentscribe.services.crew.models import MarkdownDraft

TaskMap = dict[str, Task]


def build_tasks(
    agents: AgentMap, *, language: str, target_pages: int, research_seed: str = ""
) -> TaskMap:
    """Create the four chained tasks; topic is injected via kickoff inputs."""
    seed_block = (
        f"\n\nWeb search results already gathered for you:\n{research_seed}\n"
        "Build on these real sources (use their urls verbatim); call the "
        "web_search tool for any gaps."
        if research_seed
        else ""
    )
    research = Task(
        description=(
            "Research the topic: {topic}. Use the web_search tool for anything "
            "you cannot ground in the provided results - never invent sources. "
            "Gather accurate facts and 4-6 credible sources; for every source "
            "record the real title, url, and a short cite_key "
            "(e.g. author2024keyword). Every fact must concern {topic}." + seed_block
        ),
        expected_output=(
            "A structured fact sheet: bullet-point findings grouped by theme, "
            "followed by a numbered source list with title, url and cite_key."
        ),
        agent=agents["researcher"],
    )
    write = Task(
        description=(
            f"Write a structured article in {language} of about {target_pages} "
            f"pages ({target_pages * 450} words minimum, 6-9 chapters) strictly "
            "about {topic}, based on the research context. Each chapter needs "
            "3-5 substantial paragraphs. Use Markdown: ## chapter headings, "
            "paragraphs, and inline citations [@cite_key] referencing the "
            "researcher's sources. Stay on the topic {topic} throughout."
        ),
        expected_output=(
            "A complete multi-chapter Markdown draft with inline [@cite_key] "
            "citations drawn from the research source list."
        ),
        agent=agents["writer"],
        context=[research],
    )
    edit = Task(
        description=(
            "Edit the draft for clarity and structure WITHOUT changing its "
            "meaning. Then guarantee these required elements exist, adding "
            "them where missing: (1) one Markdown table comparing relevant "
            "items; (2) one display math formula on its own line wrapped in "
            "$$...$$; (3) one figure placeholder line exactly of the form "
            "![FIGURE: <description of a chart about the topic>](chart.png); "
            "(4) one short chapter titled 'Hebrew Summary' mixing Hebrew and "
            "English sentences; (5) at least two inline citations [@cite_key]."
        ),
        expected_output=(
            "The polished full Markdown draft containing the table, the "
            "$$ formula $$, the figure placeholder, the bilingual chapter and "
            ">=2 [@cite_key] citations."
        ),
        agent=agents["editor"],
        context=[write],
    )
    latex_prep = Task(
        description=(
            "Convert the edited draft into the structured JSON contract. "
            "Split it into chapters (heading + body_markdown, preserving every "
            "table/formula/figure/citation marker verbatim). Set each "
            "required_elements flag to whether the element truly appears, "
            "list the cite_keys used, and copy the source list (title, url, "
            "cite_key) from the research context. Also fill the chart field: "
            "pick the kind (bar, barh, line, or pie) that best fits real "
            "quantities discussed in the article, with title, x_label, "
            "y_label and 3-8 labels with matching numeric values. And fill "
            "the diagram field: a block diagram of a process or architecture "
            "from the article - caption, 4-8 short node labels in flow "
            "order, and directed edges as [from_index, to_index] pairs."
        ),
        expected_output="A MarkdownDraft JSON object matching the schema exactly.",
        agent=agents["latex_engineer"],
        context=[edit, research],
        output_pydantic=MarkdownDraft,
    )
    return {"research": research, "write": write, "edit": edit, "latex_prep": latex_prep}
