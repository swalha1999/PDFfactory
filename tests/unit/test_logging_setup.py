"""Tests for shared/logging_setup.py - JSONL sink, run_id binding, redaction."""

from __future__ import annotations

import json
from pathlib import Path

from agentscribe.shared.logging_setup import (
    REDACTED,
    JsonlWriter,
    get_logger,
    make_redactor,
    setup_run_logging,
)


def test_events_written_as_jsonl_with_run_id(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    logger = setup_run_logging("run-123", log_file, console=False)
    logger.info("stage_started", stage="research")
    logger.warning("queue_full", depth=100)
    lines = [json.loads(line) for line in log_file.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["run_id"] == "run-123"
    assert lines[0]["event"] == "stage_started"
    assert lines[0]["stage"] == "research"
    assert lines[0]["level"] == "info"
    assert "ts" in lines[0]
    assert lines[1]["level"] == "warning"


def test_level_filtering(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    logger = setup_run_logging("run-1", log_file, level="WARNING", console=False)
    logger.info("ignored")
    logger.error("kept")
    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "kept"


def test_secrets_redacted_in_sink(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    logger = setup_run_logging("run-1", log_file, redact_keys=["x-custom-header"], console=False)
    logger.info(
        "api_call",
        openai_api_key="sk-live-abc",
        nested={"Authorization": "Bearer xyz", "ok": "visible"},
        headers=[{"x-custom-header": "secret-value"}],
        latency_ms=12,
    )
    event = json.loads(log_file.read_text())
    assert event["openai_api_key"] == REDACTED
    assert event["nested"]["Authorization"] == REDACTED
    assert event["nested"]["ok"] == "visible"
    assert event["headers"][0]["x-custom-header"] == REDACTED
    assert event["latency_ms"] == 12


def test_redactor_matches_common_secret_keys() -> None:
    processor = make_redactor()
    out = processor(None, "info", {"token": "t", "password": "p", "plain": 1})
    assert out == {"token": REDACTED, "password": REDACTED, "plain": 1}


def test_get_logger_binds_context(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    setup_run_logging("run-9", log_file, console=False)
    get_logger(service="latex").info("compile_pass", n=1)
    event = json.loads(log_file.read_text())
    assert event["service"] == "latex"
    assert event["run_id"] == "run-9"


def test_jsonl_writer_close(tmp_path: Path) -> None:
    writer = JsonlWriter(tmp_path / "deep" / "dir" / "f.jsonl")
    writer(None, "info", {"event": "e"})
    writer.close()
    assert (tmp_path / "deep" / "dir" / "f.jsonl").read_text().strip() == '{"event": "e"}'
