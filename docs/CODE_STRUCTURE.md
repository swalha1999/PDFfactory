# Code Structure & Engineering Conventions

> Distilled from [`agent_debate`](https://github.com/swalha1999/agent_debate)
> (our previous project, by swalha1999 & Mhmdabad). This is the blueprint we
> build PDFfactory on: same layout, same tooling, same quality gates.

## 1. Repository layout — a `uv` workspace of small packages

The project is a single repo organised as a [`uv`](https://docs.astral.sh/uv/)
workspace. Each *surface* of the product is its own package under `packages/`,
sharing one PEP 420 namespace (in agent_debate it was `agent_debate.*`; here it
will be `pdffactory.*`):

```
<project>/
├─ packages/
│  ├─ core/        # SDK — the engine; importable, drives everything programmatically
│  ├─ log/         # structured logging, cost accounting (shared dep of all others)
│  ├─ api/         # FastAPI app — thin shell over core
│  ├─ cli/         # Typer app — thin shell over core
│  └─ ui/          # web frontend consuming the API
├─ config/         # versioned, non-secret config (e.g. rate_limits.json, model_prices.json)
├─ docs/           # PRD.md, sub-PRDs (docs/prds/), TASKS.md, PROMPTS.md, this file
├─ tests/          # root-level tests; each package also owns packages/<pkg>/tests/
├─ scripts/        # repo tooling: line-limit check, secret scan, branch protection
├─ pyproject.toml  # workspace root — single source of truth for deps + tool config
├─ .env.example    # every env var documented with safe placeholders; .env is git-ignored
└─ .python-version # pins Python >= 3.12
```

Key principles:

- **`core` is the heart.** API/CLI/UI are thin shells that import the SDK —
  no business logic lives in them.
- **`log` is a shared dependency** used by every other package; one JSONL file
  per `run_id`, structured JSON + pretty console via `structlog`.
- **Every code file ≤ 150 lines.** Split into small single-responsibility
  modules instead of compressing.
- **No hard-coded values** — runtime behaviour comes from `.env`
  (via `pydantic-settings`); operational policy (rate limits, prices) lives in
  versioned `config/*.json`.

## 2. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12+, managed by `uv` | fast, reproducible, workspace support |
| LLM abstraction | **Pydantic AI** (`pydantic-ai-slim[anthropic]`) | provider-agnostic: models are config strings (`anthropic:claude-sonnet-4-6`), no ecosystem lock-in; typed agents + first-class tool calling |
| Default models | Anthropic Claude — Sonnet for workers, Opus for the judge/controller role | swappable per role via env |
| External services | behind **pluggable provider interfaces** (e.g. `SearchProvider`, default DuckDuckGo via `ddgs`) | swap vendors with one config value, no engine change |
| API | FastAPI + Uvicorn (incl. SSE streaming endpoints) | standard, async, typed |
| CLI | Typer + rich | ergonomic, typed |
| Config | pydantic-settings + `.env` / `.env.example` | portable, no secrets committed |
| Logging | structlog | machine- and human-readable |
| Lint/format/types | ruff (0 violations) + mypy `strict = true` | automated gate |
| Tests | pytest + pytest-cov, **TDD** | edge cases first-class: timeouts, malformed model output, failed tool calls |

## 3. Architectural patterns worth reusing

- **API gatekeeper**: *every* external API call (LLM, search, …) routes through
  one gatekeeper module that enforces rate limits (from `config/rate_limits.json`),
  a FIFO overflow queue, retries, and token/cost accounting. Nothing calls a
  vendor SDK directly.
- **Security gatekeeper**: validate and sanitise anything crossing a trust
  boundary — user input, tool output, web content fed back to a model. Untrusted
  text must never drive privileged actions.
- **Cost model is explicit**: per-model token prices in `config/model_prices.json`,
  per-run cost breakdown (tokens × price) in the logs; bound spend with
  word/turn limits.
- **Agents (Pydantic AI)**: each agent gets its own independent conversation
  context, a system prompt that names its registered tools and when to use
  them, and tools that are real typed functions — not prompt-only "skills".

## 4. Quality gates (enforced in CI on every push)

```bash
uv sync && uv run ruff check . && uv run ruff format --check . \
  && uv run mypy && uv run pytest --cov \
  && uv run python scripts/check_line_limit.py \
  && uv run python scripts/secret_scan.py
```

- **Coverage ≥ 85%** (`fail_under = 85` in pyproject — config, not a CI magic number).
- **TDD**: failing test first, then code (Red → Green → Refactor).
- **`main` is protected**: no direct pushes; PRs merge only when the CI
  "Quality gates" check is green (applied by a committed
  `scripts/setup_branch_protection.sh`).
- **Secret scan + line-limit check** are committed scripts held to the same
  lint/type gate as shipped code.

## 5. Documentation discipline

- **PRD before code** (`docs/PRD.md`): vision, goals, architecture, acceptance
  criteria — a new team member understands the project without asking.
- **Sub-PRDs** (`docs/prds/<mechanism>.md`) for each significant mechanism.
- **`docs/TASKS.md`**: full task breakdown by epic with status and dependencies;
  work lands as one small PR per task.
- **`docs/PROMPTS.md`**: the Prompt Book — significant AI prompts that shaped
  the project.
- README must let any developer install and run with zero prior knowledge.
- See [`Improvements_to_keep_in_mind.md`](Improvements_to_keep_in_mind.md) for
  the standing checklist distilled from past feedback.
