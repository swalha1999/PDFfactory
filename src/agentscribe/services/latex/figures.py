"""Python-generated chart for envelope item C7 (latex PRD R5; issue #21).

Emits a deterministic matplotlib script for the run's topic, executes it in
the sandbox (never on the host - ADR-005), and degrades gracefully to the
committed placeholder figure when the sandbox fails (sandbox PRD R6).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from agentscribe import constants
from agentscribe.services.crew.models import ChartSpec
from agentscribe.shared.config import Config
from agentscribe.shared.logging_setup import get_logger
from agentscribe.shared.sandbox import SandboxResult, run_in_sandbox

PLACEHOLDER = constants.TEMPLATES_DIR / "placeholder_chart.png"

SCRIPT_TEMPLATE = '''"""Auto-generated chart script for topic: {topic}"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

labels = {labels!r}
values = {values!r}

fig, ax = plt.subplots(figsize=(8, 4.5))
bars = ax.bar(labels, values, color="#4878a8")
ax.set_title({title!r})
ax.set_xlabel({x_label!r})
ax.set_ylabel({y_label!r})
ax.bar_label(bars, fmt="%g")
plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
fig.tight_layout()
fig.savefig("{output}", dpi=150)
'''

DIMENSIONS = ["Adoption", "Maturity", "Tooling", "Research", "Industry use"]


def build_chart_script(topic: str, spec: ChartSpec | None = None) -> str:
    """Chart script from the crew's content spec; deterministic fallback."""
    safe_topic = topic.replace('"""', "'").replace("\\", "")
    if spec is not None and spec.usable():
        return SCRIPT_TEMPLATE.format(
            topic=safe_topic,
            labels=[str(label)[:24] for label in spec.labels],
            values=[round(float(v), 2) for v in spec.values],
            title=spec.title[:80],
            x_label=spec.x_label[:40],
            y_label=spec.y_label[:40],
            output=constants.FIGURE_IMAGE_NAME,
        )
    digest = hashlib.sha256(topic.encode()).digest()
    return SCRIPT_TEMPLATE.format(
        topic=safe_topic,
        labels=DIMENSIONS,
        values=[40 + digest[i] % 60 for i in range(len(DIMENSIONS))],
        title=f"Key dimensions of: {safe_topic}"[:80],
        x_label="Dimension",
        y_label="Relative score",
        output=constants.FIGURE_IMAGE_NAME,
    )


def generate_chart(
    config: Config, topic: str, run_dir: Path, spec: ChartSpec | None = None
) -> tuple[Path, bool, SandboxResult]:
    """Run the chart script sandboxed; returns (path, degraded?, result).

    Attempt 1 uses the crew's content spec (when usable); the retry falls
    back to the deterministic chart, then the placeholder - a figure bug
    must never kill the run (PRD use-case 5).
    """
    log = get_logger(service="figures")
    sandbox_cfg = config.sandbox
    script = build_chart_script(topic, spec)
    result = SandboxResult(status="error")
    for attempt in (1, 2):
        result = run_in_sandbox(
            script,
            [constants.FIGURE_IMAGE_NAME],
            run_dir,
            allowed_imports=list(sandbox_cfg["allowed_imports"]),
            timeout_s=int(sandbox_cfg["timeout_s"]),
            max_output_mb=int(sandbox_cfg["max_output_mb"]),
        )
        if result.status == "success":
            log.info("chart_generated", attempt=attempt, from_spec=spec is not None)
            return run_dir / constants.FIGURE_IMAGE_NAME, False, result
        log.warning("chart_attempt_failed", attempt=attempt, status=result.status)
        script = build_chart_script(topic)  # retry with the deterministic chart
    target = run_dir / constants.FIGURE_IMAGE_NAME
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLACEHOLDER, target)
    log.warning("chart_degraded_to_placeholder")
    return target, True, result
