# Prompt Book — AgentScribe

The significant prompts that shape this system, and how they evolved.
Two kinds are documented: **(A)** the prompts the system itself runs (agent
roles and task briefs — the product's core IP), and **(B)** the prompts used
to *build* the project with an AI coding agent (the AI-driven workflow the
course asks us to make visible).

---

## A. The system's own prompts (services/crew/)

CrewAI composes each agent's system prompt from Role + Goal + Backstory, and
each task's user prompt from `description` + `expected_output` + the chained
context. Source of truth: [`agents.py`](../src/agentscribe/services/crew/agents.py)
and [`tasks.py`](../src/agentscribe/services/crew/tasks.py).

### A.1 Researcher

> **Role:** Research Analyst · **Goal:** Find accurate, current facts and
> credible sources on {topic}. · **Backstory:** "A meticulous analyst who
> verifies claims against multiple sources, always records the URL of every
> fact, and proposes a short citation key (e.g. smith2024agents) for each source."

**Iteration history.** v1 asked only for "facts and sources"; drafts then cited
nothing usable. v2 (current) bakes the *citation contract* into the backstory —
every source must carry a `cite_key` — so the bibliography stage (C11) receives
machine-usable keys instead of bare URLs.

### A.2 Writer

> **Task brief:** "Write a structured article in {language} (about
> {target_pages} pages, 6–9 chapters) on {topic} based strictly on the research
> context. Use Markdown: ## chapter headings, paragraphs, and inline citations
> [@cite_key] referencing the researcher's sources."

**Iteration history.** v1 said "write a long article" — length and structure
varied wildly. v2 pins the *shape* (chapter count, heading syntax, citation
syntax) because the downstream Markdown→LaTeX converter is deterministic: a
predictable input format is what makes the conversion testable.

### A.3 Editor — the envelope guarantor

> **Task brief (core):** "…guarantee these required elements exist, adding
> them where missing: (1) one Markdown table…; (2) one display math formula…
> wrapped in $$…$$; (3) one figure placeholder line exactly of the form
> ![FIGURE: <description>](chart.png); (4) one short chapter titled 'Hebrew
> Summary' mixing Hebrew and English sentences; (5) at least two inline
> citations [@cite_key]."

**Iteration history.** The graded checklist (C6–C11) was originally implicit
("make it complete"). The lesson: an LLM editor follows an explicit, numbered
contract far more reliably than a vibe. The exact `![FIGURE: …](chart.png)`
shape exists because the converter pattern-matches it. Belt-and-suspenders:
even if the editor misses one, `latex/engine.py` injects the missing element
deterministically — prompts steer, code guarantees.

### A.4 LaTeX Engineer — structured output

> **Task brief (core):** "Convert the edited draft into the structured JSON
> contract… Set each required_elements flag to whether the element truly
> appears, list the cite_keys used, and copy the source list from the research
> context." With `output_pydantic=MarkdownDraft`.

**Iteration history.** v1 asked for ".tex output" directly from the LLM —
fragile and unreviewable. v2 (ADR-002) keeps the LLM in Markdown/JSON space and
moves all LaTeX generation into deterministic templates. The strongest model is
reserved for this stage because schema fidelity is where quality pays.

### A.5 The figure script "prompt" that became code

The chart script (C7) was originally going to be LLM-emitted. It is now a
deterministic template (`latex/figures.py`) — values derived from the topic
hash — executed in the sandbox. Rationale: an envelope item that *must* pass
should not depend on prompt luck; the sandbox + static pre-check still treats
the script as untrusted.

---

## B. Prompts that built the project

The project was built with Claude Code driving against the document set. The
load-bearing prompts:

1. **Doc-set first.** "Write the PRD, PLAN (C4 + ADRs), TODO and one mechanism
   PRD per system (gatekeeper, sandbox, validator, observability, crew, latex)
   before any code." — Forced every later implementation step to have a
   written contract; the issues tracker was generated from these docs.
2. **The build loop.** "See the PRD and the tasks and start implementation
   until everything is satisfied; commit and push frequently; close each
   issue when finished." — One small milestone per commit, each closing its
   GitHub issue, gates green before every push.
3. **Course-rule constraints embedded in prompts.** "uv only, every file
   ≤150 lines, 0 ruff violations, mypy strict, coverage ≥85%, tests never call
   live APIs, no hard-coded values — config v1.00." — Encoding the grading
   rubric into the standing instructions meant violations surfaced as failing
   gates during development, not at submission review.
4. **Risk-first ordering.** "Verify BiDi compiles on this machine before
   building more" — surfaced the missing `luabidi.sty` early (fixed with
   `tlmgr --usermode install luabidi`, now documented in the README).

**What we learned about prompting agents:** contracts beat adjectives
(numbered requirements, exact marker syntax, typed outputs); push guarantees
out of prompts and into deterministic code wherever grading depends on them;
and keep one prompt per responsibility — the same modularity rule as the code.
