# PRD — AgentScribe: CrewAI → LaTeX Document Forge

**Document type:** Product Requirements Document (PRD)
**Project codename:** AgentScribe


> Companion documents: [`PLAN.md`](PLAN.md) (architecture) · [`TODO.md`](TODO.md) (tasks) · [`PRD_crew_pipeline.md`](PRD_crew_pipeline.md) (multi-agent mechanism) · [`PRD_latex_compiler.md`](PRD_latex_compiler.md) (LaTeX/PDF mechanism).

---

## 1. Overview and Context

### 1.1 Project goal
AgentScribe is a **CrewAI multi-agent pipeline** that takes a single topic string and autonomously produces a **polished, compilable PDF article/book** through a LaTeX toolchain. A team of cooperating agents (researcher → writer → editor → LaTeX engineer) drafts the content in Markdown, then converts and compiles it to a typeset PDF complete with cover page, table of contents, chapters, figures, a Python-generated chart, a table, a "fancy" mathematical formula, a Hebrew–English bidirectional (BiDi) chapter, and a linked bibliography.

This is the deliverable for **Exercise 03**. Per the assignment, grading is **technical and on the "envelope"** — that hyperlinks resolve, citations exist and link back, BiDi rendering is correct, tables do not overflow the page margin, and formulas render as proper math (not flat text) — **not** on factual correctness of the generated prose.

### 1.2 User problem
Producing a correctly typeset technical document is slow and error-prone: authors juggle research, prose, LaTeX syntax, BiDi typesetting, multi-pass bibliography compilation, and figure generation. Manually orchestrating an LLM for each step ("write a prompt in ChatGPT") is **not a repeatable system** — it works once and breaks at scale. AgentScribe turns that one-off prompt into a deterministic, observable **document-production pipeline** that can be re-run for any topic at any workplace.

### 1.3 Market / context analysis
The 2026 agent ecosystem (LangChain, LangGraph, CrewAI) is moving from PoC to **production**. CrewAI models a *team that works like an organization* — each agent gets a role, goal, backstory, and tools; tasks are chained by shared context. The same pattern that writes an article is reusable for reports, memos, and books. AgentScribe demonstrates the production discipline (modularity, config-driven behavior, gatekept API calls, observability) that distinguishes a professional system from a demo.

### 1.4 Target audience
- **Primary:** the course evaluator running the pipeline to verify the technical envelope.
- **Secondary:** any developer/knowledge worker who needs a reusable "topic in → typeset PDF out" generator.
- **Tertiary:** future maintainers extending the agent crew or output formats.

---

## 2. Goals, Success Metrics, and KPIs

### 2.1 Measurable goals
| # | Goal | Metric | Target |
|---|------|--------|--------|
| G1 | Produce a compilable PDF end-to-end | `lualatex`/`xelatex` exit code | 0 (clean build) |
| G2 | Meet content-envelope requirements | Checklist items present (§4.1) | 100% |
| G3 | Reliable, repeatable runs | Successful runs / 10 attempts on the same topic | ≥ 9/10 |
| G4 | Professional code quality | Ruff violations | 0 |
| G5 | Test confidence | Global coverage (`pytest --cov`) | ≥ 85% |
| G6 | Cost transparency | Token + cost report produced per run | Always |

### 2.2 Acceptance criteria (Definition of Done for the product)
The project is **accepted** when all of the following hold:
1. `uv run agentscribe --topic "<any topic>"` produces `results/<run-id>/output.pdf`.
2. The PDF contains: cover sheet (topic, author, date, course, lecturer), table of contents, chapter division, page headers/footers, ≥1 image, ≥1 Python-generated graph, ≥1 table, ≥1 math formula rendered as math, ≥1 Hebrew–English BiDi chapter, and a bibliography with **clickable** citations that jump to their reference entries.
3. A validation report confirms the **technical envelope**: links resolve, citations link back, BiDi correct, no table overflows the text width, formulas are not flat text.
4. `ruff check` → 0 violations; `uv run pytest --cov` → ≥ 85%.
5. `docs/`, `README.md`, `.env-example`, config files, and a prompt book are present.

---

## 3. Functional Requirements

### 3.1 Core features (must-have)
- **FR-1 — Topic intake.** Accept a topic string (CLI flag / config) plus optional language and length parameters. Validate non-empty input.
- **FR-2 — Research agent.** Gather facts and sources for the topic via a web-search tool routed through the API gatekeeper. Output: structured fact + source list.
- **FR-3 — Writer agent.** Transform research into a structured, multi-chapter Markdown draft (works from context, no search tool).
- **FR-4 — Editor agent.** Review for clarity/structure without changing meaning; ensure the required content elements (table, formula, figure placeholders, BiDi section, citations) are present.
- **FR-5 — LaTeX engineer agent.** Convert approved Markdown into `.tex` + `.bib`, inject the cover page, TOC, headers/footers, TikZ block diagram, and `fancy` math formulas; emit a Python script that generates the required chart.
- **FR-6 — Figure generation.** Run the agent-produced Python (matplotlib) script in a **sandbox** to render the chart image consumed by LaTeX.
- **FR-7 — Compilation orchestrator.** Run the multi-pass build (`latex → biber/bibtex → latex → latex`, ~4 passes) so all cross-references and citations resolve; surface compiler logs.
- **FR-8 — Envelope validator.** Programmatically check the PDF/build for: resolvable hyperlinks, present citations, no overfull `\hbox` beyond text width (table/figure overflow), math (not flat-text) formulas, BiDi section present.
- **FR-9 — SDK entry point.** Expose every operation (`generate_document`, `research`, `write`, `compile`, `validate`) through a single SDK class; CLI is a thin wrapper.
- **FR-10 — Run artifacts.** Persist Markdown, `.tex`, `.bib`, figures, the final PDF, logs, and a cost/token report under `results/<run-id>/`.

### 3.2 Secondary features (should-have)
- **FR-11 — Human-in-the-loop checkpoint.** Optional pause after the editor stage for manual approval before compilation.
- **FR-12 — Output format switch.** Markdown-only mode (skip LaTeX) for fast review.
- **FR-13 — Compiler selection.** Config-driven choice of LuaLaTeX (default, best Hebrew/BiDi support) or XeLaTeX.

### 3.3 Nice-to-have (could-have)
- **FR-14 — Book mode.** Multi-part `book` document class for longer outputs.
- **FR-15 — Parallel figure rendering.** Render multiple charts concurrently.

### 3.4 User stories
- *As an evaluator,* I run one command with any topic and get a PDF that passes the technical checklist, so I can grade the envelope objectively.
- *As a developer,* I import the SDK and call `generate_document(topic)` from my own service, so I can reuse the pipeline without touching internals.
- *As a maintainer,* I swap the search tool or LLM provider via config, so I am not locked to one vendor.
- *As a cost owner,* I read the per-run token/cost report, so I can forecast spend at scale.

### 3.5 Use-case scenarios
1. **Happy path:** topic → research → write → edit → LaTeX → 4-pass compile → validate → PDF + report.
2. **Compiler missing pass:** a citation link does not jump → validator flags it → orchestrator re-runs the missing pass.
3. **Flat-text formula:** LLM emits a formula as plain text → validator flags → LaTeX agent re-requests a `fancy formula`.
4. **Rate-limit hit:** search calls exceed the limit → gatekeeper queues overflow instead of crashing.
5. **Sandbox failure:** figure script errors → captured, logged, run degrades gracefully with a placeholder figure and a clear error.

---

## 4. Non-Functional Requirements

### 4.1 Content envelope (the graded checklist)
| ID | Requirement | How verified |
|----|-------------|--------------|
| C1 | ~15 pages of content | Page count of PDF |
| C2 | Cover sheet: topic, author, date, course, lecturer | Visual / text extract |
| C3 | Table of contents | `\tableofcontents` rendered with page links |
| C4 | Chapter/section division | Heading structure present |
| C5 | Page headers & footers | `fancyhdr` rendered on body pages |
| C6 | ≥1 image | `\includegraphics` resolves |
| C7 | ≥1 Python-generated graph | matplotlib script → image embedded |
| C8 | ≥1 table | `tabular`/`booktabs`, no overflow |
| C9 | ≥1 math formula as math | math environment, not flat text |
| C10 | Hebrew–English BiDi chapter | RTL↔LTR transitions render correctly |
| C11 | Bibliography with linked citations | `\cite` → reference, clickable |

### 4.2 Quality attributes (ISO/IEC 25010)
- **Functional suitability:** all FR-1…FR-10 implemented and tested.
- **Reliability:** ≥ 90% repeatable success (G3); graceful degradation on sandbox/API failure.
- **Performance:** a 15-page run completes within a documented time/token budget; figures may render in parallel.
- **Security:** no API keys in code; all secrets via env vars; **all generated Python runs in a sandbox** (Windows Sandbox / WSL) — never directly on the host. Defends against prompt-injection / tool-misuse / memory-poisoning per the lecture's agent-security section.
- **Maintainability:** SDK-layered, OOP, no duplication, every file ≤ 150 LOC, modular building blocks.
- **Portability:** runs on Windows (WSL recommended) with `uv`; LaTeX via MiKTeX.
- **Usability:** clear CLI, helpful errors, documented workflow and screenshots.

### 4.3 Engineering standards (from the submission guidelines)
- SDK architecture — no business logic in CLI.
- Centralized **API gatekeeper** for every external call; rate limits from `config/rate_limits.json`, overflow queued.
- **No hard-coded values** — config-driven; versioned config files starting at 1.00.
- **TDD**, coverage ≥ 85%, **0 Ruff** violations, files ≤ 150 LOC.
- **`uv` only** (no pip/venv); `pyproject.toml` + `uv.lock` committed.
- `.env-example` committed; `.env`, `*.key`, `*.pem` git-ignored.

---

## 5. Assumptions, Dependencies, Constraints, Out-of-Scope

### 5.1 Assumptions
- An LLM provider API key (e.g., OpenAI/Anthropic) and a web-search tool key are available via env vars.
- A LaTeX distribution (MiKTeX) with LuaLaTeX + biber is installed and on `PATH`.
- A sandbox (WSL or Windows Sandbox) is available to execute generated Python.
- Evaluator judges the **envelope**, not prose accuracy.

### 5.2 Dependencies
- **External services:** LLM provider API; web-search API (e.g., Serper) — both via the gatekeeper.
- **Tooling:** `crewai`, `crewai-tools`, `matplotlib`, `uv`, MiKTeX (LuaLaTeX/XeLaTeX, biber/BibTeX), `pytest`, `ruff`.
- **Runtime:** Python 3.10+.

### 5.3 Constraints
- BiDi (Hebrew↔English) typesetting requires LuaLaTeX (`babel`/`polyglossia`) — primary language is **English** with at least one Hebrew BiDi chapter.
- Bibliography correctness needs **~4 compilation passes**; a single pass leaves dangling citations.
- Every source file ≤ 150 LOC; coverage ≥ 85%; 0 Ruff.

### 5.4 Out of scope
- Fact-checking / guaranteeing truth of generated content.
- A graphical desktop/web UI (CLI only for this exercise).
- Real-time collaborative editing.
- Languages beyond English + a Hebrew BiDi demonstration chapter.
- Production multi-tenant deployment / hosting.

---

## 6. Timeline and Milestones

| Milestone | Deliverable | Exit criteria |
|-----------|-------------|---------------|
| **M0 — Docs approved** | PRD, PLAN, TODO, dedicated PRDs | This document set reviewed & approved |
| **M1 — Scaffold** | Package skeleton, `pyproject.toml`, config, `.env-example`, gatekeeper stub | `uv sync` works; ruff clean on skeleton |
| **M2 — Crew pipeline** | Research→Write→Edit agents producing Markdown | Markdown draft generated for a sample topic (see [`PRD_crew_pipeline.md`](PRD_crew_pipeline.md)) |
| **M3 — LaTeX engine** | Markdown→`.tex`/`.bib`, figure script, multi-pass compile | PDF builds clean (see [`PRD_latex_compiler.md`](PRD_latex_compiler.md)) |
| **M4 — Validator** | Envelope checker + report | All C1–C11 checks pass on a sample run |
| **M5 — Quality gate** | Tests ≥ 85%, 0 ruff, cost report | CI-style local gate green |
| **M6 — Polish & submit** | README, screenshots, prompt book, results notebook | Final checklist (guidelines §17) satisfied |

---

## 7. References
- Exercise 03 definition — *Mass Production of AI Agents*, L06, Dr. Yoram Segal (2026-05-29), §13.
- *Guidelines for Writing Professional Software…* V3.00, Dr. Yoram Segal (2026-03-26).
- CrewAI documentation — https://docs.crewai.com
- ISO/IEC 25010 software quality model.
