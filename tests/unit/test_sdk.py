"""Tests for the AgentScribeSDK facade: orchestration, remediation, failure paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentscribe import constants
from agentscribe.sdk.models import RunResult
from agentscribe.sdk.sdk import AgentScribeSDK
from agentscribe.services.crew.models import Chapter, MarkdownDraft, RequiredElements
from agentscribe.services.latex.engine import BuildArtifacts
from agentscribe.services.validate.report import CheckOutcome, EnvelopeReport
from agentscribe.shared.config import Config, ConfigError
from agentscribe.shared.gatekeeper import ApiGatekeeper

DRAFT = MarkdownDraft(
    title="T",
    chapters=[Chapter(heading="H", body_markdown="B")],
    required_elements=RequiredElements(),
)


def make_report(all_pass: bool, remediations: list[str] | None = None) -> EnvelopeReport:
    return EnvelopeReport(
        checks={"C1_page_count": CheckOutcome(ok=all_pass, detail="d")},
        all_pass=all_pass,
        remediations=remediations or [],
    )


@pytest.fixture
def sdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentScribeSDK:
    config = Config()
    config.override("results_dir", "ignored")
    monkeypatch.setattr(Config, "results_dir", property(lambda self: tmp_path), raising=True)
    instance = AgentScribeSDK(config, ApiGatekeeper(config))
    monkeypatch.setattr(
        "agentscribe.sdk.sdk.CrewPipeline",
        lambda config, gatekeeper: type(
            "P",
            (),
            {
                "run": lambda self, topic: (DRAFT, {"input_tokens": 10, "output_tokens": 5}),
                "stage_timings": {"research": 1.0, "write": 2.0, "edit": 0.5},
            },
        )(),
    )

    def fake_build(draft: MarkdownDraft, run_dir: Path, date: str) -> BuildArtifacts:
        (run_dir / constants.MAIN_TEX_NAME).write_text("tex")
        return BuildArtifacts(
            tex_path=run_dir / constants.MAIN_TEX_NAME,
            bib_path=run_dir / constants.REFERENCES_BIB_NAME,
        )

    monkeypatch.setattr(instance._engine, "build", fake_build)
    return instance


def patch_compile_validate(
    monkeypatch: pytest.MonkeyPatch, reports: list[EnvelopeReport]
) -> dict[str, int]:
    counts = {"compile": 0, "validate": 0}

    def fake_compile(config: Config, run_dir: Path) -> tuple[Path, list[str]]:
        counts["compile"] += 1
        pdf = run_dir / constants.OUTPUT_PDF_NAME
        pdf.write_bytes(b"%PDF")
        return pdf, ["pass1.log"]

    def fake_validate(self: AgentScribeSDK, pdf: Path, run_dir: Path, title: str) -> Any:
        report = reports[min(counts["validate"], len(reports) - 1)]
        counts["validate"] += 1
        return report

    monkeypatch.setattr("agentscribe.sdk.sdk.compile_pdf", fake_compile)
    monkeypatch.setattr(AgentScribeSDK, "validate", fake_validate)
    return counts


def test_happy_path_full_pipeline(
    sdk: AgentScribeSDK, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_compile_validate(monkeypatch, [make_report(True)])
    result = sdk.generate_document("My Topic")
    assert isinstance(result, RunResult)
    assert result.status == "success"
    assert result.all_pass
    assert result.pdf_path is not None and result.pdf_path.is_file()
    run_dir = tmp_path / result.run_id
    assert (run_dir / constants.DRAFT_MD_NAME).is_file()
    assert (run_dir / constants.COST_REPORT_JSON).is_file()
    assert (run_dir / constants.ENVELOPE_REPORT_JSON).is_file()
    cost = json.loads((run_dir / constants.COST_REPORT_JSON).read_text())
    assert set(cost["stage_timings_s"]) >= {"research", "write", "edit", "latex", "compile"}


def test_markdown_only_skips_latex(sdk: AgentScribeSDK, monkeypatch: pytest.MonkeyPatch) -> None:
    counts = patch_compile_validate(monkeypatch, [make_report(True)])
    result = sdk.generate_document("Topic", markdown_only=True)
    assert result.status == "success"
    assert result.pdf_path is None
    assert counts["compile"] == 0


def test_remediation_missing_pass_recompiles(
    sdk: AgentScribeSDK, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports = [make_report(False, ["missing_pass"]), make_report(True)]
    counts = patch_compile_validate(monkeypatch, reports)
    result = sdk.generate_document("Topic")
    assert result.status == "success"
    assert result.remediation_rounds == 1
    assert counts["compile"] == 2  # initial + one remediation recompile


def test_remediation_bounded_then_failed(
    sdk: AgentScribeSDK, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts = patch_compile_validate(monkeypatch, [make_report(False, ["flat_formula"])])
    result = sdk.generate_document("Topic")
    assert result.status == "failed"
    assert result.remediation_rounds == int(sdk.config.validator["max_remediation_rounds"])
    assert counts["compile"] == 1 + result.remediation_rounds


def test_failure_still_writes_cost_report(
    sdk: AgentScribeSDK, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def boom(config: Config, run_dir: Path) -> tuple[Path, list[str]]:
        raise RuntimeError("compiler exploded")

    monkeypatch.setattr("agentscribe.sdk.sdk.compile_pdf", boom)
    result = sdk.generate_document("Topic")
    assert result.status == "failed"
    assert result.error is not None and "compiler exploded" in result.error
    assert (tmp_path / result.run_id / constants.COST_REPORT_JSON).is_file()  # OB-2


def test_summary_renders(sdk: AgentScribeSDK, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_compile_validate(monkeypatch, [make_report(True)])
    summary = sdk.generate_document("Topic").summary()
    assert "status:  success" in summary
    assert "envelope: 1/1" in summary


def test_config_override_validates_key() -> None:
    config = Config()
    config.override("language", "he")
    assert config.language == "he"
    with pytest.raises(ConfigError):
        config.override("nope", 1)
