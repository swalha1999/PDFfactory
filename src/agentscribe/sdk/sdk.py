"""AgentScribeSDK - the single entry point for all business logic (#28, #30).

The CLI (and any future GUI/REST shell) only calls this facade: crew ->
latex build -> multi-pass compile -> validate, with a bounded
self-correction loop (R10) and a cost report written even on failure (R5).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from agentscribe import constants
from agentscribe.sdk.models import RunResult
from agentscribe.services.crew.models import MarkdownDraft
from agentscribe.services.crew.pipeline import CrewPipeline
from agentscribe.services.latex.compiler import compile_pdf
from agentscribe.services.latex.engine import LatexEngine
from agentscribe.services.validate.envelope import validate_envelope
from agentscribe.services.validate.report import EnvelopeReport
from agentscribe.shared.config import Config
from agentscribe.shared.cost import CostReporter
from agentscribe.shared.gatekeeper import ApiGatekeeper
from agentscribe.shared.logging_setup import setup_run_logging

T = TypeVar("T")


class AgentScribeSDK:
    """Facade exposing generate_document plus the individual pipeline steps."""

    def __init__(self, config: Config, gatekeeper: ApiGatekeeper) -> None:
        self.config = config
        self.gatekeeper = gatekeeper
        self._engine = LatexEngine(config)

    @classmethod
    def from_default_config(cls) -> AgentScribeSDK:
        config = Config()
        config.validate_models()
        return cls(config, ApiGatekeeper(config))

    def generate_markdown(self, topic: str) -> tuple[MarkdownDraft, dict[str, int]]:
        return CrewPipeline(self.config, self.gatekeeper).run(topic)

    def build_latex(self, draft: MarkdownDraft, run_dir: Path, date: str) -> Path:
        return self._engine.build(draft, run_dir, date).tex_path

    def compile_pdf(self, run_dir: Path) -> Path:
        return compile_pdf(self.config, run_dir)[0]

    def validate(self, pdf_path: Path, run_dir: Path, title: str) -> EnvelopeReport:
        return validate_envelope(self.config, pdf_path, run_dir, title)

    def generate_document(
        self,
        topic: str,
        *,
        language: str | None = None,
        target_pages: int | None = None,
        markdown_only: bool = False,
    ) -> RunResult:
        run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        run_dir = self.config.results_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log = setup_run_logging(
            run_id,
            run_dir / constants.RUN_LOG_NAME,
            level=self.config.log_level,
            redact_keys=self.config.redact_keys,
        )
        if language:
            self.config.override("language", language)
        if target_pages:
            self.config.override("target_pages", target_pages)
        reporter = CostReporter(self.config, run_id)
        result = RunResult(run_id=run_id, topic=topic, status="failed")
        started = time.perf_counter()
        try:
            self._run_stages(topic, run_dir, reporter, result, markdown_only)
            result.status = "success" if (markdown_only or result.all_pass) else "failed"
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            log.error("run_failed", error=result.error)
        finally:  # cost report always written, including on failure (OB-2)
            report = reporter.write(run_dir, self.gatekeeper.records, time.perf_counter() - started)
            result.cost_usd = float(report["total_usd"])
            log.info("run_finished", status=result.status, total_usd=result.cost_usd)
        return result

    def _run_stages(
        self,
        topic: str,
        run_dir: Path,
        reporter: CostReporter,
        result: RunResult,
        markdown_only: bool,
    ) -> None:
        pipeline = CrewPipeline(self.config, self.gatekeeper)
        draft, usage = pipeline.run(topic)
        for stage, seconds in pipeline.stage_timings.items():
            reporter.record_stage(stage, seconds)
        result.input_tokens = usage["input_tokens"]
        result.output_tokens = usage["output_tokens"]
        markdown_path = run_dir / constants.DRAFT_MD_NAME
        markdown_path.write_text(draft.to_markdown(), encoding="utf-8")
        result.markdown_path = markdown_path
        if markdown_only:
            return
        date = time.strftime("%Y-%m-%d")
        artifacts = self._timed(reporter, "latex", lambda: self._engine.build(draft, run_dir, date))
        result.tex_path = artifacts.tex_path
        pdf = self._timed(reporter, "compile", lambda: compile_pdf(self.config, run_dir)[0])
        report = self._timed(reporter, "validate", lambda: self.validate(pdf, run_dir, draft.title))
        report, rounds = self._self_correct(report, draft, run_dir, date, pdf)
        report.write(run_dir)
        result.pdf_path = pdf
        result.envelope = {name: c.ok for name, c in report.checks.items()}
        result.all_pass = report.all_pass
        result.remediation_rounds = rounds

    def _self_correct(
        self,
        report: EnvelopeReport,
        draft: MarkdownDraft,
        run_dir: Path,
        date: str,
        pdf: Path,
    ) -> tuple[EnvelopeReport, int]:
        """Bounded remediation loop: targeted retry per failed check (R10)."""
        max_rounds = int(self.config.validator["max_remediation_rounds"])
        rounds = 0
        while not report.all_pass and report.remediations and rounds < max_rounds:
            rounds += 1
            if report.remediations != ["missing_pass"]:
                # flat_formula / table_overflow: deterministic rebuild first
                self._engine.build(draft, run_dir, date)
            pdf = compile_pdf(self.config, run_dir)[0]
            report = self.validate(pdf, run_dir, draft.title)
        return report, rounds

    @staticmethod
    def _timed(reporter: CostReporter, stage: str, action: Callable[[], T]) -> T:
        started = time.perf_counter()
        value = action()
        reporter.record_stage(stage, time.perf_counter() - started)
        return value
