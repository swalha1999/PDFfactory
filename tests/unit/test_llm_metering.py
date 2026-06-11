"""Tests for shared/llm_metering.py - LLM calls feed the cost records (R8)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import litellm

from agentscribe.shared.config import Config
from agentscribe.shared.gatekeeper import ApiGatekeeper
from agentscribe.shared.llm_metering import register_llm_metering
from agentscribe.shared.logging_setup import REDACTED, make_redactor


class FakeUsage:
    prompt_tokens = 1200
    completion_tokens = 300


class FakeResponse:
    usage = FakeUsage()


def test_callback_records_llm_call_with_normalized_model() -> None:
    gatekeeper = ApiGatekeeper(Config())
    register_llm_metering(gatekeeper)
    callback: Any = litellm.success_callback[0]
    start = datetime(2026, 6, 11, 12, 0, 0)
    callback(
        {"model": "claude-haiku-4-5", "litellm_params": {"custom_llm_provider": "anthropic"}},
        FakeResponse(),
        start,
        start + timedelta(seconds=2),
    )
    callback({"model": "anthropic/claude-sonnet-4-6"}, FakeResponse(), start, start)
    first, second = gatekeeper.records
    assert first.service == "llm"
    assert first.model == "anthropic/claude-haiku-4-5"
    assert first.tokens == {"input": 1200, "output": 300}
    assert first.latency_ms == 2000
    assert second.model == "anthropic/claude-sonnet-4-6"


def test_tokens_field_is_not_redacted_but_secrets_are() -> None:
    processor = make_redactor()
    out = processor(
        None,
        "info",
        {"tokens": {"input": 5}, "token": "secret", "access_token": "x", "max_tokens": 100},
    )
    assert out["tokens"] == {"input": 5}  # counts are telemetry, not secrets
    assert out["max_tokens"] == 100
    assert out["token"] == REDACTED
    assert out["access_token"] == REDACTED
