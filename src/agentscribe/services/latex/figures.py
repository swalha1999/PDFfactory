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
ax.set_xlabel("Dimension")
ax.set_ylabel("Relative score")
ax.bar_label(bars, fmt="%d")
fig.tight_layout()
fig.savefig("{output}", dpi=150)
'''

DIMENSIONS = ["Adoption", "Maturity", "Tooling", "Research", "Industry use"]


def build_chart_script(topic: str) -> str:
    """Deterministic matplotlib script: values derived from the topic hash."""
    digest = hashlib.sha256(topic.encode()).digest()
    values = [40 + digest[i] % 60 for i in range(len(DIMENSIONS))]
    safe_topic = topic.replace('"""', "'").replace("\\", "")
    return SCRIPT_TEMPLATE.format(
        topic=safe_topic,
        labels=DIMENSIONS,
        values=values,
        title=f"Key dimensions of: {safe_topic}"[:80],
        output=constants.FIGURE_IMAGE_NAME,
    )


def generate_chart(config: Config, topic: str, run_dir: Path) -> tuple[Path, bool, SandboxResult]:
    """Run the chart script sandboxed; returns (path, degraded?, result).

    One retry, then the placeholder is embedded and C7 is marked degraded -
    a figure bug must never kill the run (PRD use-case 5).
    """
    log = get_logger(service="figures")
    sandbox_cfg = config.sandbox
    script = build_chart_script(topic)
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
            log.info("chart_generated", attempt=attempt)
            return run_dir / constants.FIGURE_IMAGE_NAME, False, result
        log.warning("chart_attempt_failed", attempt=attempt, status=result.status)
    target = run_dir / constants.FIGURE_IMAGE_NAME
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLACEHOLDER, target)
    log.warning("chart_degraded_to_placeholder")
    return target, True, result
