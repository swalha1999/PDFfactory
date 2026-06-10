# AI Stack — Library Choices & Rationale

**Companion to:** [`PRD.md`](PRD.md) · [`PLAN.md`](PLAN.md) (ADR-001)
**Version:** 1.00 · **Last updated:** 2026-06-10

What we use for the AI layer, why each library is the right choice for this
assignment, and what we deliberately did **not** use.

---

## 1. The constraint first

The assignment mandates the orchestration framework: *"Assignment 03: build,
using **CrewAI**, a crew of agents that writes an article/book on a topic of
your choice and produces a polished PDF via LaTeX"* (L06 §13). So "best AI
libs" here means: CrewAI used idiomatically, plus the best supporting libraries
around it — not a framework debate.

## 2. The stack

| Layer | Library | Version pin | Why this one |
|---|---|---|---|
| Agent orchestration | **`crewai`** | `>=0.80,<1` | Mandated. Role/Goal/Backstory agents, `Task(context=[...])` chaining, `Process.sequential` — exactly the researcher→writer→editor→LaTeX-engineer organization the assignment describes. |
| Agent tools | **`crewai-tools`** | matching crewai | Ships `SerperDevTool` (the lecture's own example search tool). We wrap it so every call routes through our `ApiGatekeeper` (PRD_api_gatekeeper R8). |
| LLM routing | **LiteLLM** (transitive via crewai) | — | CrewAI's built-in provider layer: a model is a config string (`"openai/gpt-4o-mini"`, `"anthropic/claude-sonnet-4-6"`, `"ollama/llama3"`). Provider swap = one config value — the lecture's modularity principle ("model replacement happens in configuration, not hard-code", L06 §9) with **zero extra dependency**. |
| Structured outputs | **`pydantic`** v2 | `>=2.9,<3` | Typed contracts between stages: `MarkdownDraft`, `BuildArtifacts`, `EnvelopeReport`, `RunResult`. CrewAI tasks support `output_pydantic`, so the crew returns validated objects, not raw strings — this is what makes the pipeline testable. |
| Config | **`pydantic-settings`** | `>=2.5,<3` | `.env` + typed settings, no hard-coded values. |
| Figures | **`matplotlib`** | `>=3.9` | Required by the envelope (C7: a Python-generated graph); `Agg` backend, executed only in the sandbox. |
| PDF validation | **`pypdf`** + **`pdfplumber`** | latest 4.x / 0.11 | Deterministic envelope checks: link annotations, page counts, text extraction (see `PRD_envelope_validator.md`). Not an AI lib — deliberately: grading-critical checks must be deterministic. |
| Logging | **`structlog`** | `>=24` | Structured JSONL + pretty console; proven in `agent_debate`. |

### Models (config, never code)
- **Default workers** (researcher/writer/editor): a fast, cheap model — e.g.
  `openai/gpt-4o-mini` or `anthropic/claude-haiku-4-5` — ~15 pages of prose is
  volume work; cost matters (goal G6).
- **LaTeX engineer + editor escalation**: a stronger model — e.g.
  `anthropic/claude-sonnet-4-6` — correct LaTeX/BiDi markup is where quality
  pays for itself.
- Both are `config/setup.json` values; the cost report names the models used.

## 3. Idiomatic CrewAI usage (what "used well" means)

1. **One agent factory** (`services/crew/agents.py`) — Role/Goal/Backstory per
   agent defined once, parameters from config (crew PRD R1).
2. **Context chaining, not copy-paste** — `Task(..., context=[prev_task])` is
   the hand-off mechanism; no manual prompt stitching (crew PRD R3).
3. **Typed task outputs** — `output_pydantic=MarkdownDraft` on the final task;
   the SDK never parses free text.
4. **Tools are gatekept** — agents never hold a raw vendor tool; every tool
   body delegates to `ApiGatekeeper.execute` (rate limits, logging, retries).
5. **Token telemetry** — usage from `crew.kickoff()` (and LiteLLM callbacks)
   flows into the cost report (observability PRD R5).
6. **`Process.sequential`** — deterministic and cheap; `hierarchical` is
   documented as the book-mode alternative (ADR-001), not the default.

## 4. What we deliberately do NOT use

| Considered | Verdict | Reason |
|---|---|---|
| LangGraph | No | Branching state machines are overkill for a near-linear 4-stage flow; the assignment targets CrewAI (ADR-001). |
| Raw LangChain | No | Same — and we'd re-implement what `Crew`/`Task` already give us. |
| LangSmith / AgentOps tracing | Not for submission | External SaaS breaks offline-reproducible grading; our structlog JSONL + cost report covers the need. Noted as future work. |
| LLM-as-judge for envelope checks | No | Grading-critical checks must be deterministic and free (validator PRD §5). |
| `instructor` / extra structured-output libs | No | CrewAI's `output_pydantic` already covers it; smaller dependency surface. |
| pip/venv/poetry | No | Guidelines mandate `uv` only. |

## 5. Risk notes

- **CrewAI moves fast** — pin `<1` upper bound in `pyproject.toml`, commit
  `uv.lock`, and keep all CrewAI imports inside `services/crew/` so an API
  change touches one package.
- **LiteLLM model strings differ per provider** — validated at startup against
  `config/model_prices.json` so a typo fails fast with a clear error, not
  mid-run.
- **Tests never call live APIs** (guidelines §6.1 rule 7): the crew is tested
  with a mocked LLM layer; one optional live smoke test is gated behind an env
  marker.
