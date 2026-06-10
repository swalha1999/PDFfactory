# PRD (Mechanism) — CrewAI Multi-Agent Pipeline

**Parent:** [`PRD.md`](PRD.md) · **Architecture:** [`PLAN.md`](PLAN.md)
**Version:** 1.00 · **Last updated:** 2026-06-03

Dedicated PRD for the central content-generation mechanism: the CrewAI crew that turns a topic into an edited, structured Markdown draft ready for LaTeX conversion.

---

## 1. Theoretical Background
CrewAI models a **team that works like an organization**. Instead of one giant prompt, work is split into clear roles; each `Agent` gets a Role, Goal, Backstory (its system prompt), and Tools. A `Task` is a unit of work (`description` + `expected_output`) assigned to an agent. A `Crew` is the envelope that links agents to tasks and preserves ordering and product hand-off; `Process` sets the order (Sequential or Hierarchical). The key glue is **Context**: one agent's output arrives as the next agent's context automatically — "no manual copy-paste."

For AgentScribe the flow is near-linear, so **`Process.sequential`** is used: Research → Write → Edit → LaTeX-prep.

## 2. Agents (the four building blocks)
| Agent | Role | Goal | Tools |
|-------|------|------|-------|
| Researcher | Market/Research Analyst | Find accurate facts + credible sources on the topic | Web search (via gatekeeper) |
| Writer | Senior Technical Writer | Turn research into a clear, multi-chapter structured draft | none (works from context) |
| Editor | Senior Editor | Check clarity/structure, ensure required elements present, don't change meaning | none |
| LaTeX engineer | LaTeX Document Engineer | Mark up content for LaTeX: flag cover/TOC/table/figure/formula/BiDi/citations | none (hand-off to LaTeX service) |

## 3. Inputs / Outputs / Setup

### 3.1 Input
- `topic: str` (required, non-empty), `language: str = "en"`, `target_pages: int = 15`.
- Cover metadata (author, date, course, lecturer) from config.

### 3.2 Output
A `MarkdownDraft` object:
```json
{
  "title": "<topic>",
  "chapters": [{ "heading": "string", "body_markdown": "string" }],
  "required_elements": {
    "table": true, "formula": true, "figure": true,
    "bidi_section": true, "citations": ["key1", "key2"]
  },
  "sources": [{ "title": "string", "url": "string", "cite_key": "string" }]
}
```

### 3.3 Setup parameters
- `process: "sequential"` (default) | `"hierarchical"`.
- `verbose: bool`, `llm_provider`, `temperature` — all from config, never hard-coded.
- `human_in_the_loop: bool` — optional pause after the Editor stage.

## 4. Specific Requirements
- **R1:** Every agent created via a single factory (`crew/agents.py`) — no duplicated agent code.
- **R2:** The search tool is invoked **only** through the `ApiGatekeeper` (rate-limited, logged).
- **R3:** Tasks chain strictly via `context=[...]` (Research→Write→Edit→LaTeX-prep).
- **R4:** The Editor must guarantee the draft contains placeholders/markers for all required envelope elements (table, formula, figure, BiDi section, ≥2 citations) so the LaTeX stage can satisfy C6–C11.
- **R5:** Crew assembly and `kickoff()` isolated in `crew/pipeline.py`; returns a typed `MarkdownDraft`, not raw text.
- **R6:** Token usage from `crew.kickoff` captured and forwarded to the cost reporter.

## 5. Performance Metrics
- Draft generation completes within the documented token/time budget for ~15 pages.
- ≥ 9/10 sample runs yield a draft with all `required_elements` true (feeds product G3).

## 6. Constraints & Alternatives
- **Constraint:** sequential process keeps cost predictable and ordering deterministic.
- **Alternative considered — Hierarchical (Manager agent):** more flexible but higher token cost and less determinism; reserved for future "book mode."
- **Alternative considered — single mega-prompt:** rejected — not modular, not repeatable, hard to debug.

## 7. Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| CP-1 | Valid topic, happy path | `MarkdownDraft` with all required_elements true |
| CP-2 | Empty topic | Raises `ValueError` before any API call |
| CP-3 | Search API over rate limit | Gatekeeper queues; no crash; draft still produced |
| CP-4 | Editor missing a required element | Editor re-prompts writer / marker injected; element present |
| CP-5 | Provider error (mocked) | Graceful error, logged, surfaced to SDK |
| CP-6 | Token accounting | Cost reporter receives non-zero in/out token counts |

> Tests mock the LLM and search APIs (no live external calls, per guidelines §6.1 rule 7).
