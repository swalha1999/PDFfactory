"""Tests for shared/cost.py - OB-1/OB-2/OB-4/OB-5 from the observability PRD."""

from __future__ import annotations

import json
from pathlib import Path

from agentscribe import constants
from agentscribe.shared.config import Config
from agentscribe.shared.cost import CostReporter
from agentscribe.shared.rate_limit import CallRecord

WORKER = "anthropic/claude-haiku-4-5"


def rec(service: str, model: str | None = None, tin: int = 0, tout: int = 0) -> CallRecord:
    return CallRecord(
        service=service, started_at=0.0, model=model, tokens={"input": tin, "output": tout}
    )


def test_totals_match_usage_exactly() -> None:
    config = Config()
    reporter = CostReporter(config, "run-1")
    records = [
        rec("llm", WORKER, 1_000_000, 0),
        rec("llm", WORKER, 0, 1_000_000),
        rec("search"),
        rec("search"),
    ]
    report = reporter.build_report(records, duration_s=12.5)
    price = config.model_price(WORKER)
    entry = report["by_model"][0]
    assert entry["calls"] == 2
    assert entry["usd"] == round(price["input"] + price["output"], 6)
    assert report["total_usd"] == entry["usd"]
    assert report["search_calls"] == 2
    assert report["projected_usd"]["per_100_runs"] == round(entry["usd"] * 100, 4)


def test_unknown_model_flagged_not_crashing() -> None:
    report = CostReporter(Config(), "run-2").build_report(
        [rec("llm", "mystery/model-x", 500, 500)], duration_s=1
    )
    assert report["by_model"][0]["unknown_price"] is True
    assert report["by_model"][0]["usd"] == 0.0
    assert report["unknown_price_models"] == ["mystery/model-x"]


def test_stage_timings_recorded() -> None:
    reporter = CostReporter(Config(), "run-3")
    for stage in constants.Stage:
        reporter.record_stage(stage.value, 1.5)
    report = reporter.build_report([], duration_s=9)
    assert set(report["stage_timings_s"]) == {s.value for s in constants.Stage}
    assert all(v > 0 for v in report["stage_timings_s"].values())


def test_write_persists_json_and_markdown(tmp_path: Path) -> None:
    reporter = CostReporter(Config(), "run-4")
    reporter.record_stage("research", 2.0)
    reporter.write(tmp_path, [rec("llm", WORKER, 100, 200)], duration_s=3.3)
    data = json.loads((tmp_path / constants.COST_REPORT_JSON).read_text())
    assert data["run_id"] == "run-4"
    md = (tmp_path / constants.COST_REPORT_MD).read_text()
    assert WORKER in md
    assert "Projected cost at scale" in md
    assert "research" in md


def test_empty_run_still_reports(tmp_path: Path) -> None:
    report = CostReporter(Config(), "run-5").write(tmp_path, [], duration_s=0.1)
    assert report["total_usd"] == 0.0
    assert (tmp_path / constants.COST_REPORT_JSON).is_file()
