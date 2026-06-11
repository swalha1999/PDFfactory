"""GK-7: architectural fitness test - no vendor/HTTP imports outside shared/.

Every external call must route through the gatekeeper (PRD_api_gatekeeper R1).
"""

from __future__ import annotations

import ast
from pathlib import Path

from agentscribe import constants

FORBIDDEN = {"requests", "httpx", "urllib3", "openai", "anthropic", "litellm", "aiohttp"}
SRC = constants.PROJECT_ROOT / "src" / "agentscribe"


def iter_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_no_http_or_vendor_imports_outside_shared() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.parent.name == "shared":
            continue
        bad = iter_imports(path) & FORBIDDEN
        if bad:
            offenders.append(f"{path.relative_to(SRC)}: {sorted(bad)}")
    assert not offenders, f"External-call imports outside shared/: {offenders}"
