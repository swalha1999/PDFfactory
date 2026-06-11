"""Agent factory - the four crew members defined once (crew PRD R1).

Role/Goal/Backstory per agent; models come from config (worker model for
researcher/writer/editor, the stronger engineer model for LaTeX prep).
"""

from __future__ import annotations

from typing import Any

from crewai import LLM, Agent

from agentscribe.shared.config import Config

AgentMap = dict[str, Agent]


def build_agents(config: Config, search_tool: Any) -> AgentMap:
    """Create researcher, writer, editor and latex_engineer agents."""
    # LLM objects (not bare strings) so max_tokens also applies to CrewAI's
    # internal converter calls (structured output of a ~15-page draft).
    worker = LLM(model=config.worker_model, max_tokens=config.worker_max_tokens)
    engineer = LLM(model=config.engineer_model, max_tokens=config.engineer_max_tokens)
    researcher = Agent(
        role="Research Analyst",
        goal="Find accurate, current facts and credible sources on {topic}.",
        backstory=(
            "A meticulous analyst who verifies claims against multiple sources, "
            "always records the URL of every fact, and proposes a short "
            "citation key (e.g. smith2024agents) for each source."
        ),
        tools=[search_tool],
        llm=worker,
        verbose=False,
    )
    writer = Agent(
        role="Senior Technical Writer",
        goal="Turn research into a clear, multi-chapter article draft in Markdown.",
        backstory=(
            "An experienced author of long-form technical articles who writes "
            "well-structured chapters with smooth narrative flow, citing the "
            "researcher's sources inline as [@cite_key]."
        ),
        llm=worker,
        verbose=False,
    )
    editor = Agent(
        role="Senior Editor",
        goal=(
            "Polish clarity and structure without changing meaning, and ensure "
            "every required document element is present."
        ),
        backstory=(
            "A demanding editor for a technical publisher. The publishing "
            "checklist requires: at least one Markdown table, one display math "
            "formula, one figure placeholder, one Hebrew-English bilingual "
            "section, and at least two inline citations [@key]."
        ),
        llm=worker,
        verbose=False,
    )
    latex_engineer = Agent(
        role="LaTeX Document Engineer",
        goal=(
            "Restructure the edited draft into the exact JSON contract the "
            "LaTeX toolchain consumes, preserving all content and markers."
        ),
        backstory=(
            "A typesetting specialist who knows the downstream LaTeX pipeline "
            "renders chapters, tables, math, BiDi text and citations from a "
            "strict structured format - nothing may be lost in conversion."
        ),
        llm=engineer,
        verbose=False,
    )
    return {
        "researcher": researcher,
        "writer": writer,
        "editor": editor,
        "latex_engineer": latex_engineer,
    }
