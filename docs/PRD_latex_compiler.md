# PRD (Mechanism) — LaTeX Engine & Multi-Pass Compiler

**Parent:** [`PRD.md`](PRD.md) · **Architecture:** [`PLAN.md`](PLAN.md)
**Version:** 1.00 · **Last updated:** 2026-06-03

Dedicated PRD for the mechanism that converts the edited Markdown draft into a typeset PDF: template injection, figure generation, BiDi typesetting, and the multi-pass bibliography compile.

---

## 1. Theoretical Background
A correct LaTeX document with a bibliography requires **multiple compilation passes**. The first `latex` pass writes `.aux` entries; `biber`/`bibtex` resolves the bibliography from the `.bib` file; subsequent `latex` passes pull citations and cross-references back in and stabilize page numbers / the table of contents. The assignment specifies **~4 passes** (`latex → biber → latex → latex`): if clicking a citation does not jump to its reference, a pass is missing.

BiDi (Hebrew↔English) typesetting needs an engine with full Unicode + font shaping. **LuaLaTeX** (with `babel`/`polyglossia` + a Hebrew-capable font) is the default; **XeLaTeX** is the allowed alternative. `pdfLaTeX` is unsuitable for Hebrew.

## 2. Inputs / Outputs / Setup

### 2.1 Input
- `MarkdownDraft` (from the crew pipeline) + cover metadata + `config/setup.json`.

### 2.2 Output (`BuildArtifacts` → final PDF)
```json
{
  "tex_path": "results/<run-id>/main.tex",
  "bib_path": "results/<run-id>/references.bib",
  "figure_paths": ["results/<run-id>/figures/chart_01.png"],
  "pdf_path": "results/<run-id>/output.pdf",
  "compiler_logs": ["pass1.log", "biber.log", "pass2.log", "pass3.log"]
}
```

### 2.3 Setup parameters (config, never hard-coded)
- `compiler`: `"lualatex"` (default) | `"xelatex"`.
- `compile_passes`: `4`.
- `document_class`: `"article"` (default) | `"book"`.
- `bib_backend`: `"biber"` (default) | `"bibtex"`.

## 3. Specific Requirements (maps to content envelope C1–C11)
- **R1 — Cover sheet (C2):** title=topic, author, date, course, lecturer.
- **R2 — TOC + structure (C3, C4):** `\tableofcontents`, chapters/sections with hyperref links.
- **R3 — Headers/footers (C5):** `fancyhdr` on body pages.
- **R4 — Image (C6):** `\includegraphics` of a static asset that resolves.
- **R5 — Python graph (C7):** emit a matplotlib script, run it **in the sandbox**, embed the produced PNG.
- **R6 — Table (C8):** `booktabs`/`tabularx` sized to text width — **must not overflow** the margin.
- **R7 — Fancy formula (C9):** a real math environment (`equation`/`align`), never flat text. If the model emits flat text, re-request a "fancy formula."
- **R8 — BiDi chapter (C10):** at least one chapter mixing Hebrew (RTL) and English (LTR) with correct directional transitions.
- **R9 — Bibliography (C11):** `.bib` entries + `\cite`; clickable citations jump to references (requires R10).
- **R10 — Multi-pass compile:** run `compile_passes` passes with the configured backend; abort with logs on non-zero exit.
- **R11 — TikZ:** at least one TikZ block diagram (satisfies the "diagram" expectation and C6 if used as the image).

## 4. Performance / Quality Metrics
- Clean build: final pass exit code 0; no unresolved `??` citations in the log.
- Zero overfull `\hbox` warnings exceeding text width on table/figure lines (parsed by the validator).
- ~15-page PDF builds within the documented time budget.

## 5. Constraints, Alternatives & Rationale
- **Default LuaLaTeX** — best Hebrew/BiDi support (ADR-003).
- **Markdown-first** conversion (ADR-002) — defer LaTeX fragility until content is final.
- **Alternative — single-pass compile:** rejected; leaves dangling citations (the assignment's named failure mode).
- **Alternative — pandoc for md→tex:** acceptable as an internal helper, but templating (cover/headers/BiDi/TikZ) is custom; keep conversion deterministic and testable.

## 6. Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| LC-1 | Full draft → compile | `output.pdf` exists; final exit code 0 |
| LC-2 | Missing bib pass | Validator flags dangling `\cite`; orchestrator re-runs pass |
| LC-3 | Flat-text formula in input | Detected; re-wrapped in math env (C9) |
| LC-4 | Wide table | Rendered within text width; no overfull box (C8) |
| LC-5 | BiDi chapter | RTL↔LTR transitions render; no reversed runs (C10) |
| LC-6 | Figure script errors in sandbox | Captured + logged; graceful degradation with placeholder |
| LC-7 | XeLaTeX selected via config | Builds clean with `compiler="xelatex"` |

> Compiler invocations and sandbox runs are integration-tested against small fixtures; unit tests cover the deterministic `md_to_tex` conversion and template rendering with mocked file I/O.
