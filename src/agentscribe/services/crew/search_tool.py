"""Gatekept web-search tool for the researcher agent (crew PRD R2, #17).

Agents never hold a raw vendor tool: the tool body delegates to
``ApiGatekeeper.execute`` so every search is rate-limited, queued, retried,
and logged (AI_STACK §3 item 4).
"""

from __future__ import annotations

from typing import Any

from crewai.tools import tool

from agentscribe.shared.gatekeeper import ApiGatekeeper
from agentscribe.shared.search_client import serper_search


def build_search_tool(gatekeeper: ApiGatekeeper) -> Any:
    """Create the crew search tool bound to the run's gatekeeper."""

    @tool("web_search")  # type: ignore[misc]  # crewai's decorator is untyped
    def web_search(query: str) -> str:
        """Search the web for current facts and credible sources about a query.

        Returns result lines as `- title | url` followed by a snippet; use the
        urls as citation sources.
        """
        result = gatekeeper.execute("search", serper_search, query)
        return str(result)

    return web_search
