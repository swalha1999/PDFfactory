"""Anthropic compatibility shim for CrewAI's ReAct message flow.

CrewAI 0.203 appends tool results as a trailing *assistant* message before
re-calling the model; newer Claude models reject conversations that end
with an assistant turn ("model does not support assistant message
prefill"). This LLM subclass re-roles such a trailing message as a user
observation, which is the shape Anthropic expects.
"""

from __future__ import annotations

from typing import Any

from crewai import LLM


def ensure_user_turn_last(messages: Any) -> Any:
    """Return messages with a trailing assistant turn re-rolled as user."""
    if not isinstance(messages, list) or not messages:
        return messages
    last = messages[-1]
    if isinstance(last, dict) and last.get("role") == "assistant":
        return [*messages[:-1], {**last, "role": "user"}]
    return messages


class AnthropicSafeLLM(LLM):  # type: ignore[misc]  # crewai.LLM is untyped
    """crewai.LLM that never sends a conversation ending with assistant."""

    def call(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
        return super().call(ensure_user_turn_last(messages), *args, **kwargs)
