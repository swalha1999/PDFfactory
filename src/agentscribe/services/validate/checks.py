"""The eleven envelope checks C1-C11 (validator PRD R1-R9).

Each check is a pure function over the pre-loaded ValidationContext and
returns a CheckResult with a pass flag, human detail, and an optional named
remediation action (R10).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentscribe.services.validate.bidi import contains_hebrew, rtl_applied
from agentscribe.services.validate.context import ValidationContext

LATIN_RE = re.compile(r"[A-Za-z]{3,}")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")
SECTION_RE = re.compile(r"\\(?:section|chapter)\{")
MATH_ENV_RE = re.compile(r"\\begin\{(?:equation|align|gather|multline)\*?\}")
CITE_RE = re.compile(r"\\cite\{([^}]+)\}")
UNDEFINED_CITE_RE = re.compile(r"Citation `([^']+)' .*undefined", re.I)
FLAT_FORMULA_RE = re.compile(r"\b[A-Za-z]\s*=\s*[A-Za-z0-9][A-Za-z0-9^_+\-*/]{2,}")


@dataclass
class CheckResult:
    ok: bool
    detail: str
    remediation: str | None = None


def c1_page_count(ctx: ValidationContext, target: int, tolerance: int) -> CheckResult:
    ok = ctx.page_count >= target - tolerance
    return CheckResult(ok, f"{ctx.page_count} pages (target ~{target} -{tolerance})")


def c2_cover(ctx: ValidationContext, cover: dict[str, str], title: str) -> CheckResult:
    page1 = ctx.page_texts[0] if ctx.page_texts else ""
    wanted = [title.split()[0], cover["author"], cover["course"], cover["lecturer"]]
    missing = [w for w in wanted if w not in page1]
    return CheckResult(not missing, "cover fields found" if not missing else f"missing: {missing}")


def c3_toc(ctx: ValidationContext) -> CheckResult:
    has_toc = "\\tableofcontents" in ctx.tex and "Contents" in ctx.full_text
    ok = has_toc and ctx.internal_link_count > 0
    return CheckResult(ok, f"TOC present; {ctx.internal_link_count} internal links")


def c4_chapters(ctx: ValidationContext) -> CheckResult:
    count = len(SECTION_RE.findall(ctx.tex))
    return CheckResult(count >= 3, f"{count} sections detected")


def c5_headers(ctx: ValidationContext) -> CheckResult:
    ok = "\\pagestyle{fancy}" in ctx.tex and "fancyhdr" in ctx.logs
    return CheckResult(ok, "fancyhdr configured and loaded" if ok else "fancyhdr missing")


def c6_image(ctx: ValidationContext) -> CheckResult:
    targets = INCLUDEGRAPHICS_RE.findall(ctx.tex)
    missing = [t for t in targets if not (ctx.build_dir / t).is_file()]
    ok = bool(targets) and not missing
    return CheckResult(ok, f"{len(targets)} \\includegraphics; missing files: {missing or 'none'}")


def c7_python_graph(ctx: ValidationContext, chart_name: str) -> CheckResult:
    embedded = chart_name in ctx.tex and (ctx.build_dir / chart_name).is_file()
    from_sandbox = any(
        entry.get("file") == chart_name and entry.get("source") == "sandbox"
        for entry in ctx.manifest
    )
    if embedded and from_sandbox:
        return CheckResult(True, f"{chart_name} embedded; sandbox provenance verified")
    if embedded:
        return CheckResult(False, f"{chart_name} embedded but degraded (no sandbox manifest)")
    return CheckResult(False, f"{chart_name} not embedded")


def c8_table(ctx: ValidationContext, threshold_pt: float, margin_pt: float) -> CheckResult:
    """Table present and nothing crosses the right margin - measured directly
    on the PDF geometry (compiler-log overfulls include phantom warnings from
    tabularx's trial measurement passes, so logs are not a reliable oracle)."""
    has_table = "\\begin{tabularx}" in ctx.tex or "\\begin{tabular}" in ctx.tex
    if not has_table:
        return CheckResult(False, "no table environment found")
    right_limit = ctx.page_width - margin_pt + threshold_pt
    overflows = [
        f"page {page}: content reaches x={x1:.0f}pt (limit {right_limit:.0f}pt)"
        for page, x1 in enumerate(ctx.page_max_x1, start=1)
        if ctx.page_width and x1 > right_limit
    ]
    if overflows:
        return CheckResult(False, "; ".join(overflows), remediation="table_overflow")
    return CheckResult(True, "table present; no content crosses the text-width margin")


def c9_math(ctx: ValidationContext) -> CheckResult:
    envs = len(MATH_ENV_RE.findall(ctx.tex))
    if envs == 0:
        return CheckResult(False, "no display-math environment", remediation="flat_formula")
    prose = re.sub(r"\\begin\{(equation|align)\*?\}.*?\\end\{\1\*?\}", "", ctx.tex, flags=re.S)
    flat = FLAT_FORMULA_RE.search(
        "\n".join(line for line in prose.splitlines() if not line.lstrip().startswith("\\"))
    )
    if flat and "$" not in flat.group(0):
        return CheckResult(
            False, f"flat-text formula suspect: {flat.group(0)!r}", remediation="flat_formula"
        )
    return CheckResult(True, f"{envs} display-math environment(s)")


def c10_bidi(ctx: ValidationContext) -> CheckResult:
    has_env = "\\texthebrew" in ctx.tex or "\\begin{hebrew}" in ctx.tex
    hebrew = contains_hebrew(ctx.full_text)
    latin = bool(LATIN_RE.search(ctx.full_text))
    rtl_ok = rtl_applied(ctx.full_text) if hebrew else False
    ok = has_env and hebrew and latin and rtl_ok
    detail = (
        f"hebrew env={has_env}, hebrew text={hebrew}, latin text={latin}, "
        f"rtl direction={'ok' if rtl_ok else 'REVERSED - engine laid Hebrew out LTR'}"
    )
    return CheckResult(ok, detail)


def c11_bibliography(ctx: ValidationContext) -> CheckResult:
    keys = {k.strip() for group in CITE_RE.findall(ctx.tex) for k in group.split(",")}
    undefined = set(UNDEFINED_CITE_RE.findall((ctx.final_log or ctx.logs) + ctx.aux))
    missing_in_bib = [k for k in keys if f"{{{k}," not in ctx.bib.replace("@misc{", "{")]
    if not keys:
        return CheckResult(False, "no \\cite commands found")
    if undefined:
        return CheckResult(
            False, f"undefined citations: {sorted(undefined)}", remediation="missing_pass"
        )
    if missing_in_bib:
        return CheckResult(False, f"cite keys missing from .bib: {missing_in_bib}")
    ok = ctx.internal_link_count > 0
    detail = f"{len(keys)} cite keys resolved; internal links={ctx.internal_link_count}"
    return CheckResult(ok, detail, remediation=None if ok else "missing_pass")
