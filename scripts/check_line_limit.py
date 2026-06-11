"""CI gate: every source file stays <= MAX_LINES lines (guidelines; TODO T6.4).

Applies to src/ and scripts/. Splitting into single-responsibility modules
is the fix - never compressing code to dodge the limit.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_LINES = 150
CHECKED_DIRS = ("src", "scripts")


def find_violations(root: Path) -> list[str]:
    violations = []
    for directory in CHECKED_DIRS:
        for path in sorted((root / directory).rglob("*.py")):
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count > MAX_LINES:
                violations.append(f"{path.relative_to(root)}: {count} lines (max {MAX_LINES})")
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = find_violations(root)
    for violation in violations:
        print(f"LINE-LIMIT: {violation}")
    if violations:
        return 1
    print(f"line-limit check OK (all files <= {MAX_LINES} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
