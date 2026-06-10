# PRD (Mechanism) — Envelope Validator & Self-Correction Loop

**Parent:** [`PRD.md`](PRD.md) · **Architecture:** [`PLAN.md`](PLAN.md) (ADR-007)
**Version:** 1.00 · **Last updated:** 2026-06-10

Dedicated PRD for the component that programmatically verifies the **graded
technical envelope** (PRD §4.1, C1–C11) on the built PDF and compiler logs, and
drives targeted self-correction when a check fails.

---

## 1. Theoretical Background

The assignment is explicit: grading is technical, on the envelope — links
resolve, citations exist and link back, BiDi renders correctly, tables don't
overflow the margin, formulas are real math — not on content correctness
(L06 §13). A system that *checks its own envelope* before handing the PDF to
the evaluator converts grading criteria into executable acceptance tests. This
also closes the production feedback loop the lecture demands ("monitor, fix and
adjust"): a failed check triggers a *specific* remediation (re-run a compile
pass, re-request a fancy formula) rather than a blind full re-run.

## 2. Inputs / Outputs / Setup

### 2.1 Input
- `pdf_path` — the built PDF.
- `build_dir` — the run directory containing `.tex`, `.bib`, `.aux`, `.log`
  files and figure assets.

### 2.2 Output — `EnvelopeReport`
```json
{
  "checks": {
    "C1_page_count":   { "pass": true,  "detail": "16 pages (target ~15)" },
    "C2_cover":        { "pass": true,  "detail": "title/author/date/course/lecturer found" },
    "C3_toc":          { "pass": true,  "detail": "TOC with hyperlinked entries" },
    "C4_chapters":     { "pass": true,  "detail": "6 sections detected" },
    "C5_headers":      { "pass": true,  "detail": "fancyhdr on body pages" },
    "C6_image":        { "pass": true,  "detail": "2 \\includegraphics resolved" },
    "C7_python_graph": { "pass": true,  "detail": "figures/chart_01.png embedded" },
    "C8_table":        { "pass": true,  "detail": "1 table, 0 overfull hbox on table lines" },
    "C9_math":         { "pass": true,  "detail": "3 equation envs; no flat-text formula heuristic hit" },
    "C10_bidi":        { "pass": true,  "detail": "RTL run + LTR run in chapter 4" },
    "C11_bibliography":{ "pass": true,  "detail": "5 \\cite keys, 0 unresolved, links present" }
  },
  "all_pass": true,
  "remediations": []
}
```

### 2.3 Setup parameters (config)
- `page_count_target` (15) and `page_count_tolerance` (±3).
- `overfull_hbox_threshold_pt` (allowed slack before a table/figure counts as
  overflowing the text width).
- `max_remediation_rounds` (default 2) — bound on the self-correction loop.

## 3. Specific Requirements — how each check is implemented
- **R1 (C1):** page count via `pypdf` — within target ± tolerance.
- **R2 (C2):** extract page-1 text (`pdfplumber`); assert the five cover fields
  from config metadata appear.
- **R3 (C3, C11 links):** inspect PDF link annotations (`pypdf`): TOC entries
  and `\cite` marks must carry internal GoTo links whose destinations exist.
- **R4 (C4, C5):** parse `main.tex` for sectioning commands; assert `fancyhdr`
  package + non-empty header/footer config; cross-check `.log` loaded it.
- **R5 (C6, C7):** every `\includegraphics` target exists in `build_dir`; at
  least one is the sandbox-generated chart (matched by manifest from the
  figures service, see `PRD_sandbox_runner.md`).
- **R6 (C8):** parse compiler `.log` for `Overfull \hbox` warnings; map line
  numbers to table environments; fail if overflow beyond threshold.
- **R7 (C9):** assert ≥1 display-math environment in the `.tex`; heuristic
  flat-text detector (formula-like text outside math mode, e.g. `E = mc^2` in
  prose) flags C9 for remediation.
- **R8 (C10):** assert the BiDi chapter contains both a Hebrew-script run and a
  Latin-script run in the extracted text, and the `.tex` uses the
  `babel`/`polyglossia` RTL environment.
- **R9 (C11):** `.log` and `.aux` contain no `Citation ... undefined` and no
  `??`; every `\cite` key exists in `references.bib`.
- **R10 — Remediation mapping:** each failed check maps to one named action:
  `missing_pass` → re-run compile sequence; `flat_formula` → re-invoke the
  LaTeX agent with a "fancy formula" request for that fragment; `table_overflow`
  → re-render table with `tabularx`/smaller width; bounded by
  `max_remediation_rounds`, then surfaced as a failed run with the report.
- **R11 — Report artifact:** the JSON report plus a human-readable Markdown
  summary are written to `results/<run-id>/` and returned by the SDK.

## 4. Performance Metrics
- Full validation of a ~15-page PDF completes in < 10 s.
- False-pass rate 0 on the negative fixtures (a deliberately broken PDF for
  each check must fail exactly that check) — this is the core of the test suite.
- ≥ 9/10 sample runs reach `all_pass: true` within `max_remediation_rounds`
  (feeds product goal G3).

## 5. Constraints & Alternatives
- **Constraint:** PDF text extraction of Hebrew can reorder glyphs; the BiDi
  check therefore asserts *presence of both scripts* + correct `.tex`
  environments rather than visual order (documented heuristic, ADR-007).
- **Alternative — manual visual checklist:** rejected as the only mechanism —
  not repeatable, not testable; kept as a final human step in the README.
- **Alternative — LLM-as-judge on the PDF:** rejected for grading-critical
  checks (non-deterministic, costs tokens); deterministic parsing is auditable.

## 6. Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| EV-1 | Golden fixture PDF (all C1–C11 satisfied) | `all_pass: true` |
| EV-2 | PDF built with one compile pass missing | C11 fails; remediation `missing_pass` |
| EV-3 | Flat-text formula fixture | C9 fails; remediation `flat_formula` |
| EV-4 | Overfull table fixture | C8 fails with the offending line in `detail` |
| EV-5 | Missing Hebrew chapter | C10 fails |
| EV-6 | Broken TOC/citation links | C3/C11 fail listing dead destinations |
| EV-7 | Remediation loop exceeds rounds | Run marked failed; report persisted; exit code ≠ 0 |

> Fixtures are tiny pre-built PDFs/logs committed under `tests/fixtures/` —
> validator tests never invoke LaTeX or an LLM.
