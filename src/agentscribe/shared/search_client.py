"""Serper web-search HTTP client (PRD_api_gatekeeper R1).

The only module allowed to speak HTTP for search. Never called directly by
agents - the crew's search tool routes through ``ApiGatekeeper.execute``.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from agentscribe.shared.rate_limit import TRANSIENT_STATUS_CODES, TransientApiError

SERPER_URL = "https://google.serper.dev/search"
TIMEOUT_S = 30


class SearchKeyMissingError(RuntimeError):
    """SERPER_API_KEY is not set in the environment."""


def serper_search(query: str, *, num_results: int = 5) -> str:
    """Search the web via Serper; returns a compact text block of results."""
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        raise SearchKeyMissingError("SERPER_API_KEY missing - see .env-example")
    response = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=TIMEOUT_S,
    )
    if response.status_code in TRANSIENT_STATUS_CODES:
        raise TransientApiError(f"Serper HTTP {response.status_code}")
    response.raise_for_status()
    return format_results(response.json())


def format_results(payload: dict[str, Any]) -> str:
    """Flatten Serper's organic results into lines the LLM can cite from."""
    lines = []
    for item in payload.get("organic", []):
        title = item.get("title", "untitled")
        link = item.get("link", "")
        snippet = item.get("snippet", "")
        lines.append(f"- {title} | {link}\n  {snippet}")
    return "\n".join(lines) if lines else "(no results)"
