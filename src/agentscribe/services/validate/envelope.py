"""Envelope validator orchestrator: run all C1-C11 checks (#26; ADR-007)."""

from __future__ import annotations

from pathlib import Path

from agentscribe import constants
from agentscribe.services.validate import checks
from agentscribe.services.validate.context import load_context
from agentscribe.services.validate.report import CheckOutcome, EnvelopeReport
from agentscribe.shared.config import Config
from agentscribe.shared.logging_setup import get_logger


def validate_envelope(
    config: Config, pdf_path: Path, build_dir: Path, title: str
) -> EnvelopeReport:
    """Validate the built PDF + artifacts; returns the full report (R11)."""
    log = get_logger(service="validator")
    ctx = load_context(pdf_path, build_dir)
    validator_cfg = config.validator
    threshold = float(validator_cfg["overfull_hbox_threshold_pt"])
    tolerance = int(validator_cfg["page_count_tolerance"])
    results = {
        "C1_page_count": checks.c1_page_count(ctx, config.target_pages, tolerance),
        "C2_cover": checks.c2_cover(ctx, config.cover, title),
        "C3_toc": checks.c3_toc(ctx),
        "C4_chapters": checks.c4_chapters(ctx),
        "C5_headers": checks.c5_headers(ctx),
        "C6_image": checks.c6_image(ctx),
        "C7_python_graph": checks.c7_python_graph(ctx, constants.FIGURE_IMAGE_NAME),
        "C8_table": checks.c8_table(ctx, threshold),
        "C9_math": checks.c9_math(ctx),
        "C10_bidi": checks.c10_bidi(ctx),
        "C11_bibliography": checks.c11_bibliography(ctx),
    }
    outcomes = {
        name: CheckOutcome(ok=r.ok, detail=r.detail, remediation=r.remediation)
        for name, r in results.items()
    }
    remediations = sorted({r.remediation for r in results.values() if r.remediation})
    report = EnvelopeReport(
        checks=outcomes,
        all_pass=all(r.ok for r in results.values()),
        remediations=remediations,
    )
    log.info(
        "envelope_validated",
        all_pass=report.all_pass,
        failed=[n for n, r in results.items() if not r.ok],
        remediations=remediations,
    )
    return report
