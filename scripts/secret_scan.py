"""CI gate: no secrets committed to the repository (guidelines §4.3; #34).

Scans tracked text files for key-shaped strings (provider key prefixes,
assignments of real-looking values to *_API_KEY variables). Placeholders
in .env-example are allowed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{32,}"),  # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),  # OpenAI
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub PAT
    re.compile(
        r"""(?i)\b[A-Z_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*['"][A-Za-z0-9_/+-]{24,}['"]"""
    ),
]
SKIP_SUFFIXES = {".png", ".jpg", ".pdf", ".lock", ".ipynb"}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [root / line for line in output.splitlines() if line]


def scan(root: Path) -> list[str]:
    findings = []
    for path in tracked_files(root):
        if path.suffix in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "your-" in line or "example" in str(path.name):  # documented placeholders
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(root)}:{lineno}: {pattern.pattern[:40]}")
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan(root)
    for finding in findings:
        print(f"SECRET-SCAN: {finding}")
    if findings:
        return 1
    print("secret scan OK (no committed secrets found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
