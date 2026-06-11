"""Render every crew-supplied chart (C7 plus extras) for one run.

The primary chart keeps the chart.png contract (figure placeholder + C7
provenance check). Additional usable specs render to chart_2.png... and are
emitted as an extra "Data Visualizations" section; a failing extra chart is
skipped - only the primary degrades to the placeholder.
"""

from __future__ import annotations

from pathlib import Path

from agentscribe.services.crew.models import ChartSpec, MarkdownDraft
from agentscribe.services.latex.figures import build_chart_script, generate_chart
from agentscribe.services.latex.md_inline import escape_tex
from agentscribe.shared.config import Config
from agentscribe.shared.logging_setup import get_logger
from agentscribe.shared.sandbox import run_in_sandbox

EXTRA_SECTION = "\\section{Data Visualizations}\nFurther charts generated for this article.\n"

FIGURE_TEX = """\\begin{{figure}}[ht!]
\\centering
\\includegraphics[width=0.85\\textwidth]{{{filename}}}
\\caption{{{caption}}}
\\end{{figure}}
"""


def _render_extra(
    config: Config, topic: str, run_dir: Path, spec: ChartSpec, filename: str
) -> list[dict[str, str]] | None:
    """Sandbox-run one extra chart; returns its manifest or None on failure."""
    sandbox_cfg = config.sandbox
    result = run_in_sandbox(
        build_chart_script(topic, spec, output=filename),
        [filename],
        run_dir,
        allowed_imports=list(sandbox_cfg["allowed_imports"]),
        timeout_s=int(sandbox_cfg["timeout_s"]),
        max_output_mb=int(sandbox_cfg["max_output_mb"]),
    )
    return result.manifest if result.status == "success" else None


def generate_figures(
    config: Config, draft: MarkdownDraft, run_dir: Path
) -> tuple[list[Path], bool, list[dict[str, str]], str]:
    """All charts for the draft: (paths, primary_degraded, manifest, extra_tex)."""
    log = get_logger(service="figures")
    specs = draft.usable_charts()
    primary_spec = specs[0] if specs else None
    primary_path, degraded, primary_result = generate_chart(
        config, draft.title, run_dir, spec=primary_spec
    )
    paths = [primary_path]
    manifest = list(primary_result.manifest)
    extra_tex_parts: list[str] = []
    for index, spec in enumerate(specs[1:], start=2):
        filename = f"chart_{index}.png"
        extra_manifest = _render_extra(config, draft.title, run_dir, spec, filename)
        if extra_manifest is None:
            log.warning("extra_chart_skipped", filename=filename, title=spec.title)
            continue
        manifest += extra_manifest
        paths.append(run_dir / filename)
        extra_tex_parts.append(
            FIGURE_TEX.format(filename=filename, caption=escape_tex(spec.title[:120]))
        )
    extra_tex = EXTRA_SECTION + "\n".join(extra_tex_parts) if extra_tex_parts else ""
    log.info("figures_done", charts=len(paths), degraded_primary=degraded)
    return paths, degraded, manifest, extra_tex
