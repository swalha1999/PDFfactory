"""LLM call metering via LiteLLM success callbacks (gatekeeper PRD R8).

CrewAI routes model calls through LiteLLM internally; this hook records a
CallRecord per completed LLM call (model, latency, tokens) into the
gatekeeper so the cost report shows real per-model numbers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import litellm

from agentscribe.shared.gatekeeper import ApiGatekeeper
from agentscribe.shared.rate_limit import CallRecord


def _normalize_model(kwargs: dict[str, Any]) -> str:
    """Return 'provider/model' to match config/model_prices.json keys."""
    model = str(kwargs.get("model", "unknown"))
    if "/" in model:
        return model
    params = kwargs.get("litellm_params") or {}
    provider = str(params.get("custom_llm_provider") or "unknown")
    return f"{provider}/{model}"


def register_llm_metering(gatekeeper: ApiGatekeeper) -> None:
    """Install (or replace) the success callback feeding the gatekeeper."""
    # Newer Claude models reject assistant-prefill messages that CrewAI's
    # ReAct tool prompt emits; modify_params lets LiteLLM reshape the
    # conversation to Anthropic's requirements.
    litellm.modify_params = True

    def record_call(
        kwargs: dict[str, Any],
        completion_response: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        usage = getattr(completion_response, "usage", None)
        record = CallRecord(
            service="llm",
            started_at=start_time.timestamp(),
            latency_ms=(end_time - start_time).total_seconds() * 1000,
            tokens={
                "input": int(getattr(usage, "prompt_tokens", 0) or 0),
                "output": int(getattr(usage, "completion_tokens", 0) or 0),
            },
            model=_normalize_model(kwargs),
            outcome="success",
        )
        gatekeeper.records.append(record)

    litellm.success_callback = [record_call]
