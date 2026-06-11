"""End-to-end integration test (#32): topic -> PDF -> all C1-C11 pass.

The crew is mocked (guidelines §6.1: tests never call live APIs); the LaTeX
build, sandboxed chart, 4-pass compile and envelope validation are real.
Skipped where no LaTeX toolchain exists (CI) - run locally before submitting.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from crewai import Crew

from agentscribe.sdk.sdk import AgentScribeSDK
from agentscribe.services.crew.models import (
    Chapter,
    MarkdownDraft,
    RequiredElements,
    Source,
)
from agentscribe.shared.config import Config

needs_latex = pytest.mark.skipif(
    shutil.which("xelatex") is None or shutil.which("bibtex") is None,
    reason="LaTeX toolchain not installed",
)

PARAGRAPH = (
    "Multi-agent systems decompose complex knowledge work into specialized "
    "roles that cooperate through shared context. A researcher gathers and "
    "verifies facts, a writer shapes them into narrative, an editor enforces "
    "structure and completeness, and an engineer prepares the material for "
    "typesetting. This division of labor mirrors how professional teams "
    "operate, and it is what turns a one-off prompt into a repeatable "
    "production system that can be monitored, measured and improved over "
    "time. The economics of such a pipeline are explicit: every call is "
    "metered, every stage is timed, and every run ends with a cost report "
    "that makes scaling decisions evidence-based rather than guesswork. "
)


def full_draft() -> MarkdownDraft:
    chapters = [
        Chapter(
            heading=f"Chapter {i}: Perspective {i} on Production Agents",
            body_markdown="\n\n".join([PARAGRAPH * 4] * 3) + "\n\nAs noted in [@crewai2026docs].",
        )
        for i in range(1, 9)
    ]
    return MarkdownDraft(
        title="Production-Grade Multi-Agent Document Pipelines",
        chapters=chapters,
        required_elements=RequiredElements(),
        sources=[
            Source(
                title="CrewAI Documentation",
                url="https://docs.crewai.com",
                cite_key="crewai2026docs",
            ),
            Source(title="ISO/IEC 25010", url="https://iso.org/25010", cite_key="iso25010"),
        ],
    )


@needs_latex
def test_e2e_topic_to_pdf_all_envelope_checks_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "results_dir", property(lambda self: tmp_path), raising=True)

    class FakeUsage:
        prompt_tokens, completion_tokens, total_tokens = 5000, 9000, 14000

    class FakeOutput:
        pydantic = full_draft()
        raw = ""
        token_usage = FakeUsage()

    def fake_kickoff(self: Crew, inputs: dict[str, Any] | None = None) -> FakeOutput:
        return FakeOutput()

    monkeypatch.setattr(Crew, "kickoff", fake_kickoff)
    sdk = AgentScribeSDK.from_default_config()
    result = sdk.generate_document("Production-Grade Multi-Agent Document Pipelines")
    assert result.error is None
    assert result.pdf_path is not None and result.pdf_path.is_file()
    failed = [name for name, ok in result.envelope.items() if not ok]
    assert result.all_pass, f"failed checks: {failed}"
    assert result.status == "success"
    run_dir = tmp_path / result.run_id
    for artifact in (
        "draft.md",
        "main.tex",
        "references.bib",
        "chart.png",
        "envelope_report.json",
        "envelope_report.md",
        "cost_report.json",
        "cost_report.md",
        "run.jsonl",
    ):
        assert (run_dir / artifact).is_file(), artifact
