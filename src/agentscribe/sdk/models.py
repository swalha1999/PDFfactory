"""SDK result contract returned to every consumer (PLAN §6.1)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class RunResult(BaseModel):
    """Everything a caller needs to know about one generation run."""

    run_id: str
    topic: str
    status: str  # success | failed | aborted
    error: str | None = None
    pdf_path: Path | None = None
    markdown_path: Path | None = None
    tex_path: Path | None = None
    envelope: dict[str, bool] = Field(default_factory=dict)
    all_pass: bool = False
    remediation_rounds: int = 0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    def summary(self) -> str:
        """Human-readable one-screen summary for the CLI."""
        lines = [
            f"run_id:  {self.run_id}",
            f"topic:   {self.topic}",
            f"status:  {self.status}",
        ]
        if self.error:
            lines.append(f"error:   {self.error}")
        if self.pdf_path:
            lines.append(f"pdf:     {self.pdf_path}")
        if self.markdown_path:
            lines.append(f"draft:   {self.markdown_path}")
        if self.envelope:
            passed = sum(self.envelope.values())
            lines.append(f"envelope: {passed}/{len(self.envelope)} checks pass")
            failed = [name for name, ok in self.envelope.items() if not ok]
            if failed:
                lines.append(f"failed:  {', '.join(failed)}")
        lines.append(
            f"cost:    ${self.cost_usd:.4f} "
            f"({self.input_tokens} in / {self.output_tokens} out tokens)"
        )
        return "\n".join(lines)
