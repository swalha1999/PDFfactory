"""Tests for main.py - the CLI must stay a logic-free wrapper (#29)."""

from __future__ import annotations

import pytest

from agentscribe.main import build_parser, main


def test_parser_accepts_all_flags() -> None:
    args = build_parser().parse_args(
        ["--topic", "X", "--language", "he", "--target-pages", "10", "--markdown-only"]
    )
    assert args.topic == "X"
    assert args.language == "he"
    assert args.target_pages == 10
    assert args.markdown_only is True


def test_topic_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_blank_topic_exits_2_before_any_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--topic", "   "]) == 2
    assert "non-empty" in capsys.readouterr().err


def test_main_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeResult:
        status = "success"

        @staticmethod
        def summary() -> str:
            return "ok"

    class FakeSDK:
        @classmethod
        def from_default_config(cls) -> FakeSDK:
            return cls()

        def generate_document(self, topic: str, **kwargs: object) -> FakeResult:
            calls["topic"] = topic
            calls.update(kwargs)
            return FakeResult()

    monkeypatch.setattr("agentscribe.sdk.sdk.AgentScribeSDK", FakeSDK)
    assert main(["--topic", "Agents", "--markdown-only"]) == 0
    assert calls["topic"] == "Agents"
    assert calls["markdown_only"] is True
