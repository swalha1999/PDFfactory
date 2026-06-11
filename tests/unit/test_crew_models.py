"""Tests for crew models and the gatekept search client/tool."""

from __future__ import annotations

from typing import Any

import pytest

from agentscribe.services.crew.models import Chapter, MarkdownDraft, RequiredElements, Source
from agentscribe.shared.rate_limit import TransientApiError
from agentscribe.shared.search_client import SearchKeyMissingError, format_results, serper_search


def make_draft(**elements: Any) -> MarkdownDraft:
    return MarkdownDraft(
        title="T",
        chapters=[Chapter(heading="Intro", body_markdown="Hello [@a2024]")],
        required_elements=RequiredElements(**elements),
        sources=[Source(title="S", url="https://x", cite_key="a2024")],
    )


def test_required_elements_all_present() -> None:
    ok = RequiredElements(
        table=True, formula=True, figure=True, bidi_section=True, citations=["a", "b"]
    )
    assert ok.all_present()
    assert not RequiredElements(
        table=True, formula=True, figure=True, bidi_section=True, citations=["a"]
    ).all_present()
    assert not RequiredElements().all_present()


def test_to_markdown_renders_title_and_chapters() -> None:
    md = make_draft().to_markdown()
    assert md.startswith("# T")
    assert "## Intro" in md
    assert "[@a2024]" in md


def test_format_results_flattens_organic() -> None:
    text = format_results({"organic": [{"title": "A", "link": "https://a", "snippet": "s1"}]})
    assert "A | https://a" in text
    assert format_results({}) == "(no results)"


def test_serper_search_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    with pytest.raises(SearchKeyMissingError):
        serper_search("q")


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_serper_search_happy_and_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPER_API_KEY", "k")
    monkeypatch.setattr(
        "agentscribe.shared.search_client.requests.post",
        lambda *a, **k: FakeResponse(200, {"organic": [{"title": "T", "link": "u"}]}),
    )
    assert "T | u" in serper_search("q")
    monkeypatch.setattr(
        "agentscribe.shared.search_client.requests.post",
        lambda *a, **k: FakeResponse(429, {}),
    )
    with pytest.raises(TransientApiError):
        serper_search("q")


def test_search_tool_routes_through_gatekeeper() -> None:
    from agentscribe.services.crew.search_tool import build_search_tool

    calls: list[tuple[str, Any]] = []

    class StubGatekeeper:
        def execute(self, service: str, call: Any, *args: Any, **kwargs: Any) -> str:
            calls.append((service, args))
            return "results"

    tool = build_search_tool(StubGatekeeper())  # type: ignore[arg-type]
    assert tool.run(query="agents in production") == "results"
    assert calls == [("search", ("agents in production",))]


def test_trailing_assistant_turn_rerolled_for_anthropic() -> None:
    from agentscribe.services.crew.llm_compat import ensure_user_turn_last

    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": "tool result"},
    ]
    fixed = ensure_user_turn_last(messages)
    assert fixed[-1] == {"role": "user", "content": "tool result"}
    assert fixed[:-1] == messages[:-1]
    untouched = [{"role": "user", "content": "u"}]
    assert ensure_user_turn_last(untouched) == untouched
    assert ensure_user_turn_last("plain string") == "plain string"
