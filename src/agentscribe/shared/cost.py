"""Token/cost reporter - the per-run "Spec Sheet" (PRD_observability_cost R5-R6).

Aggregates gatekeeper CallRecords, prices them from config/model_prices.json
(no price constant in code), and writes JSON + Markdown reports at run end -
including for failed runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentscribe import constants
from agentscribe.shared.config import Config, ConfigError
from agentscribe.shared.logging_setup import get_logger
from agentscribe.shared.rate_limit import CallRecord

SCALE_POINTS = (10, 100, 1000)


class CostReporter:
    """Aggregates usage, prices it, and persists the per-run cost report."""

    def __init__(self, config: Config, run_id: str) -> None:
        self._config = config
        self.run_id = run_id
        self.stage_timings_s: dict[str, float] = {}

    def record_stage(self, stage: str, seconds: float) -> None:
        """Stage telemetry feeding stage_timings_s (R4)."""
        self.stage_timings_s[stage] = round(seconds, 3)

    def _price(self, model: str, tokens: dict[str, int]) -> tuple[float, bool]:
        try:
            price = self._config.model_price(model)
        except ConfigError:
            return 0.0, True  # OB-4: unknown model flagged, never a crash
        usd = (
            tokens.get("input", 0) * price["input"] + tokens.get("output", 0) * price["output"]
        ) / 1_000_000
        return usd, False

    def build_report(self, records: list[CallRecord], duration_s: float) -> dict[str, Any]:
        by_model: dict[str, dict[str, Any]] = {}
        search_calls = 0
        unknown: set[str] = set()
        for record in records:
            if record.service == "search":
                search_calls += 1
            if record.model is None:
                continue
            entry = by_model.setdefault(
                record.model,
                {"model": record.model, "calls": 0, "input_tokens": 0, "output_tokens": 0},
            )
            entry["calls"] += 1
            entry["input_tokens"] += record.tokens.get("input", 0)
            entry["output_tokens"] += record.tokens.get("output", 0)
        for entry in by_model.values():
            usd, is_unknown = self._price(
                entry["model"],
                {"input": entry["input_tokens"], "output": entry["output_tokens"]},
            )
            entry["usd"] = round(usd, 6)
            if is_unknown:
                entry["unknown_price"] = True
                unknown.add(entry["model"])
        total = round(sum(e["usd"] for e in by_model.values()), 6)
        return {
            "run_id": self.run_id,
            "by_model": sorted(by_model.values(), key=lambda e: str(e["model"])),
            "search_calls": search_calls,
            "total_usd": total,
            "duration_s": round(duration_s, 1),
            "stage_timings_s": dict(self.stage_timings_s),
            "unknown_price_models": sorted(unknown),
            "projected_usd": {f"per_{n}_runs": round(total * n, 4) for n in SCALE_POINTS},
        }

    def write(self, run_dir: Path, records: list[CallRecord], duration_s: float) -> dict[str, Any]:
        """Persist cost_report.json + cost_report.md under the run dir (R5)."""
        report = self.build_report(records, duration_s)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / constants.COST_REPORT_JSON).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (run_dir / constants.COST_REPORT_MD).write_text(_to_markdown(report), encoding="utf-8")
        get_logger(service="cost").info(
            "cost_report_written", total_usd=report["total_usd"], duration_s=report["duration_s"]
        )
        return report


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Cost Report — run `{report['run_id']}`",
        "",
        "| Model | Calls | Input tokens | Output tokens | USD |",
        "|-------|------:|-------------:|--------------:|----:|",
    ]
    for e in report["by_model"]:
        flag = " (no price!)" if e.get("unknown_price") else ""
        lines.append(
            f"| {e['model']}{flag} | {e['calls']} | {e['input_tokens']} "
            f"| {e['output_tokens']} | ${e['usd']:.4f} |"
        )
    lines += [
        "",
        f"**Search calls:** {report['search_calls']}  ",
        f"**Total:** ${report['total_usd']:.4f}  ",
        f"**Duration:** {report['duration_s']} s",
        "",
        "## Stage timings",
        "",
    ]
    lines += [f"- {stage}: {sec} s" for stage, sec in report["stage_timings_s"].items()]
    lines += ["", "## Projected cost at scale (linear)", ""]
    lines += [f"- {k.replace('_', ' ')}: ${v:.2f}" for k, v in report["projected_usd"].items()]
    return "\n".join(lines) + "\n"
