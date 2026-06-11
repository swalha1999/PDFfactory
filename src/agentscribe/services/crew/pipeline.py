"""Crew assembly and kickoff (crew PRD R5-R6; issues #16, #18).

``CrewPipeline.run(topic)`` validates input, assembles the sequential crew,
runs it, captures token usage for the cost reporter, and optionally pauses
at a human checkpoint after the editor stage (FR-11).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from crewai import Crew, Process

from agentscribe.services.crew.agents import build_agents
from agentscribe.services.crew.models import MarkdownDraft
from agentscribe.services.crew.search_tool import build_search_tool
from agentscribe.services.crew.tasks import build_tasks
from agentscribe.shared.config import Config
from agentscribe.shared.gatekeeper import ApiGatekeeper
from agentscribe.shared.logging_setup import get_logger

# Receives the edited draft text; returns True to continue, False to abort.
Checkpoint = Callable[[str], bool]


class PipelineAbortedError(RuntimeError):
    """The human reviewer rejected the draft at the checkpoint."""


class DraftParseError(RuntimeError):
    """The crew finished but did not return a valid MarkdownDraft."""


class CrewPipeline:
    """Topic in -> validated MarkdownDraft + token usage out."""

    def __init__(
        self,
        config: Config,
        gatekeeper: ApiGatekeeper,
        *,
        checkpoint: Checkpoint | None = None,
    ) -> None:
        self._config = config
        self._gatekeeper = gatekeeper
        self._checkpoint = checkpoint
        self._log = get_logger(service="crew")
        self.stage_timings: dict[str, float] = {}

    def _build_crew(self) -> tuple[Crew, dict[str, Any]]:
        search_tool = build_search_tool(self._gatekeeper)
        agents = build_agents(self._config, search_tool)
        tasks = build_tasks(
            agents,
            language=self._config.language,
            target_pages=self._config.target_pages,
        )
        crew = Crew(
            agents=list(agents.values()),
            tasks=list(tasks.values()),
            process=Process.sequential,
            verbose=False,
        )
        return crew, {"tasks": tasks}

    def run(self, topic: str) -> tuple[MarkdownDraft, dict[str, int]]:
        """Run the crew for a topic; returns the draft and token usage (R6)."""
        if not topic or not topic.strip():
            raise ValueError("topic must be a non-empty string")  # CP-2: before any API call
        crew, parts = self._build_crew()
        self._arm_stage_timers(parts["tasks"])
        self._log.info("crew_kickoff", topic=topic)
        output = crew.kickoff(inputs={"topic": topic.strip()})
        draft = self._extract_draft(output)
        usage = self._extract_usage(output)
        self._log.info(
            "crew_finished",
            chapters=len(draft.chapters),
            elements_ok=draft.required_elements.all_present(),
            **usage,
        )
        self._maybe_checkpoint(parts["tasks"]["edit"])
        return draft, usage

    def _arm_stage_timers(self, tasks: dict[str, Any]) -> None:
        """Record per-task durations via CrewAI task callbacks (OB-5)."""
        last = [time.perf_counter()]

        def make_callback(stage: str) -> Callable[[Any], None]:
            def callback(_output: Any) -> None:
                now = time.perf_counter()
                self.stage_timings[stage] = now - last[0]
                last[0] = now

            return callback

        for name, stage in (("research", "research"), ("write", "write"), ("edit", "edit")):
            tasks[name].callback = make_callback(stage)

    def _maybe_checkpoint(self, edit_task: Any) -> None:
        """Optional human-in-the-loop pause after the editor stage (FR-11)."""
        if not self._config.human_in_the_loop or self._checkpoint is None:
            return
        edited_text = str(getattr(getattr(edit_task, "output", None), "raw", ""))
        if not self._checkpoint(edited_text):
            self._log.warning("checkpoint_rejected")
            raise PipelineAbortedError("human checkpoint rejected the edited draft")
        self._log.info("checkpoint_approved")

    @staticmethod
    def _extract_draft(output: Any) -> MarkdownDraft:
        pydantic_out = getattr(output, "pydantic", None)
        if isinstance(pydantic_out, MarkdownDraft):
            return pydantic_out
        raw = getattr(output, "raw", None) or str(output)
        try:
            return MarkdownDraft.model_validate_json(raw)
        except ValueError as exc:
            raise DraftParseError(f"crew output is not a MarkdownDraft: {exc}") from exc

    @staticmethod
    def _extract_usage(output: Any) -> dict[str, int]:
        usage = getattr(output, "token_usage", None)
        return {
            "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }
