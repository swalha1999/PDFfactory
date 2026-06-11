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
{plot_code}
ax.set_title({title!r})
fig.tight_layout()
fig.savefig("{output}", dpi=150)
'''

PLOT_CODE = {
    "bar": """bars = ax.bar(labels, values, color="#4878a8")
ax.bar_label(bars, fmt="%g")
ax.set_xlabel({x_label!r})
ax.set_ylabel({y_label!r})
plt.setp(ax.get_xticklabels(), rotation=15, ha="right")""",
    "barh": """bars = ax.barh(labels, values, color="#6a9a58")
ax.bar_label(bars, fmt="%g")
ax.set_xlabel({y_label!r})
ax.invert_yaxis()""",
    "line": """ax.plot(labels, values, marker="o", color="#a85478", linewidth=2)
ax.set_xlabel({x_label!r})
ax.set_ylabel({y_label!r})
ax.grid(alpha=0.3)""",
    "pie": """ax.pie(values, labels=labels, autopct="%1.0f%%",
       wedgeprops={{"edgecolor": "white"}})
ax.axis("equal")""",
}

DIMENSIONS = ["Adoption", "Maturity", "Tooling", "Research", "Industry use"]
FALLBACK_KINDS = ("bar", "barh", "line")


def _render(
    topic: str, kind: str, title: str, x: str, y: str, labels: list[str], values: list[float]
) -> str:
    plot_code = PLOT_CODE[kind].format(x_label=x[:40], y_label=y[:40])
    return SCRIPT_TEMPLATE.format(
        topic=topic.replace('"""', "'").replace("\\", ""),
        labels=[str(label)[:24] for label in labels],
        values=[round(float(v), 2) for v in values],
        plot_code=plot_code,
        title=title[:80],
        output=constants.FIGURE_IMAGE_NAME,
    )


def build_chart_script(topic: str, spec: ChartSpec | None = None) -> str:
    """Chart script from the crew's content spec; deterministic fallback
    (whose kind also varies by topic so repeated samples differ)."""
    if spec is not None and spec.usable():
        return _render(
            topic,
            spec.kind,
            spec.title,
            spec.x_label,
            spec.y_label,
            spec.labels,
            spec.values,
        )
    digest = hashlib.sha256(topic.encode()).digest()
    kind = FALLBACK_KINDS[digest[5] % len(FALLBACK_KINDS)]
    return _render(
        topic,
        kind,
        f"Key dimensions of: {topic}",
        "Dimension",
        "Relative score",
        DIMENSIONS,
        [float(40 + digest[i] % 60) for i in range(len(DIMENSIONS))],
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
