"""Tests for crew agents/tasks/pipeline - PRD_crew_pipeline CP-1..CP-6 (mocked)."""

from __future__ import annotations

from typing import Any

import pytest
from crewai import Crew

from agentscribe.services.crew.agents import build_agents
from agentscribe.services.crew.models import MarkdownDraft
from agentscribe.services.crew.pipeline import (
    CrewPipeline,
    DraftParseError,
    PipelineAbortedError,
)
from agentscribe.services.crew.tasks import build_tasks
from agentscribe.shared.config import Config
from agentscribe.shared.gatekeeper import ApiGatekeeper

DRAFT_JSON = {
    "title": "Topic",
    "chapters": [{"heading": "Intro", "body_markdown": "text [@a] [@b]"}],
    "required_elements": {
        "table": True,
        "formula": True,
        "figure": True,
        "bidi_section": True,
        "citations": ["a", "b"],
    },
    "sources": [{"title": "S", "url": "https://s", "cite_key": "a"}],
}


class FakeUsage:
    prompt_tokens = 1200
    completion_tokens = 800
    total_tokens = 2000


class FakeOutput:
    def __init__(self, pydantic: MarkdownDraft | None, raw: str = "") -> None:
        self.pydantic = pydantic
        self.raw = raw
        self.token_usage = FakeUsage()


@pytest.fixture
def pipeline_parts(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    config = Config()
    gatekeeper = ApiGatekeeper(config)
    captured: dict[str, Any] = {"config": config, "gatekeeper": gatekeeper}

    def fake_kickoff(self: Crew, inputs: dict[str, Any] | None = None) -> FakeOutput:
        captured["inputs"] = inputs
        return FakeOutput(MarkdownDraft.model_validate(DRAFT_JSON))

    monkeypatch.setattr(Crew, "kickoff", fake_kickoff)
    return captured


def make_test_tool() -> Any:
    from agentscribe.services.crew.search_tool import build_search_tool

    class StubGatekeeper:
        def execute(self, service: str, call: Any, *args: Any, **kwargs: Any) -> str:
            return "results"

    return build_search_tool(StubGatekeeper())  # type: ignore[arg-type]


def test_agent_factory_builds_four_agents() -> None:
    config = Config()
    agents = build_agents(config, search_tool=make_test_tool())
    assert set(agents) == {"researcher", "writer", "editor", "latex_engineer"}
    assert agents["researcher"].role == "Research Analyst"


def test_tasks_chain_via_context() -> None:
    agents = build_agents(Config(), search_tool=make_test_tool())
    tasks = build_tasks(agents, language="en", target_pages=15)
    assert tasks["write"].context == [tasks["research"]]
    assert tasks["edit"].context == [tasks["write"]]
    assert tasks["latex_prep"].context == [tasks["edit"], tasks["research"]]
    assert tasks["latex_prep"].output_pydantic is MarkdownDraft


def test_cp1_happy_path_returns_typed_draft(pipeline_parts: dict[str, Any]) -> None:
    pipeline = CrewPipeline(pipeline_parts["config"], pipeline_parts["gatekeeper"])
    draft, usage = pipeline.run("  Agentic AI in Production  ")
    assert isinstance(draft, MarkdownDraft)
    assert draft.required_elements.all_present()
    assert pipeline_parts["inputs"] == {"topic": "Agentic AI in Production"}
    assert usage == {"input_tokens": 1200, "output_tokens": 800, "total_tokens": 2000}  # CP-6


@pytest.mark.parametrize("bad_topic", ["", "   "])
def test_cp2_empty_topic_rejected_before_any_call(bad_topic: str) -> None:
    pipeline = CrewPipeline(Config(), ApiGatekeeper(Config()))
    with pytest.raises(ValueError, match="non-empty"):
        pipeline.run(bad_topic)


def test_cp5_invalid_crew_output_raises_draft_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Crew, "kickoff", lambda self, inputs=None: FakeOutput(None, raw="not json"))
    pipeline = CrewPipeline(Config(), ApiGatekeeper(Config()))
    with pytest.raises(DraftParseError):
        pipeline.run("Topic")


def test_checkpoint_rejection_aborts(pipeline_parts: dict[str, Any]) -> None:
    config: Config = pipeline_parts["config"]
    config._setup["human_in_the_loop"] = True
    pipeline = CrewPipeline(config, pipeline_parts["gatekeeper"], checkpoint=lambda text: False)
    with pytest.raises(PipelineAbortedError):
        pipeline.run("Topic")


def test_checkpoint_approval_continues(pipeline_parts: dict[str, Any]) -> None:
    config: Config = pipeline_parts["config"]
    config._setup["human_in_the_loop"] = True
    seen: list[str] = []

    def approve(text: str) -> bool:
        seen.append(text)
        return True

    pipeline = CrewPipeline(config, pipeline_parts["gatekeeper"], checkpoint=approve)
    draft, _ = pipeline.run("Topic")
    assert draft.title == "Topic"
    assert len(seen) == 1
