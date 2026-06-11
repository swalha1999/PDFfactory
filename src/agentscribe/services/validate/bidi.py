"""BiDi direction heuristics for the C10 check (validator PRD R8).

PDF text extraction is visual-order: when RTL was applied correctly,
Hebrew final letters (which only occur at logical word ends) appear at
the *start* of extracted words; trailing finals mean the engine laid the
Hebrew out left-to-right (mirrored glyphs - the LuaLaTeX/luabidi bug).
"""

from __future__ import annotations

import re

HEBREW_RE = re.compile(r"[֐-׿]")
HEBREW_FINALS = "ךםןףץ"
HEBREW_WORD_RE = re.compile(r"[֐-׿]{2,}")


def contains_hebrew(text: str) -> bool:
    return bool(HEBREW_RE.search(text))


def rtl_applied(text: str) -> bool:
    """True when extracted Hebrew looks correctly right-to-left rendered."""
    words = HEBREW_WORD_RE.findall(text)
    starts = sum(word[0] in HEBREW_FINALS for word in words)
    ends = sum(word[-1] in HEBREW_FINALS for word in words)
    if starts == ends == 0:
        return True  # no final letters - direction inconclusive, trust the env
    return starts >= ends
