"""EnvelopeReport artifact: JSON + Markdown per run (#27; validator PRD R11)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentscribe import constants


class CheckOutcome(BaseModel):
    """One envelope check's verdict."""

    ok: bool
    detail: str
    remediation: str | None = None


class EnvelopeReport(BaseModel):
    """All C1-C11 verdicts plus the named remediation actions (R10)."""

    checks: dict[str, CheckOutcome]
    all_pass: bool
    remediations: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# Envelope Report",
            "",
            f"**Overall: {'ALL CHECKS PASS' if self.all_pass else 'FAILURES PRESENT'}**",
            "",
            "| Check | Result | Detail |",
            "|-------|--------|--------|",
        ]
        for name, outcome in self.checks.items():
            mark = "PASS" if outcome.ok else "FAIL"
            lines.append(f"| {name} | {mark} | {outcome.detail} |")
        if self.remediations:
            lines += ["", "**Remediations suggested:** " + ", ".join(self.remediations)]
        return "\n".join(lines) + "\n"

    def write(self, run_dir: Path) -> None:
        """Persist envelope_report.json + envelope_report.md under the run dir."""
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / constants.ENVELOPE_REPORT_JSON).write_text(
            self.model_dump_json(indent=2), encoding="utf-8"
        )
        (run_dir / constants.ENVELOPE_REPORT_MD).write_text(self.to_markdown(), encoding="utf-8")
