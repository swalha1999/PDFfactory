# AgentScribe — CrewAI → LaTeX Document Forge

Give it a topic; get back a polished, compilable **PDF article** — cover page,
table of contents, chapters, a Python-generated chart, a TikZ diagram, a real
math formula, a Hebrew–English BiDi chapter, and a clickable bibliography —
produced end-to-end by a crew of cooperating AI agents and a deterministic
LaTeX toolchain.

```
topic ──> Researcher ──> Writer ──> Editor ──> LaTeX Engineer
              │ (web search via gatekeeper)         │ typed MarkdownDraft
              ▼                                     ▼
       results/<run-id>/   <── validate <── 4-pass compile <── main.tex + chart (sandboxed)
```

Built for **Exercise 03 — Mass Production of AI Agents** (Dr. Yoram Segal).
Full docs: [`docs/PRD.md`](docs/PRD.md) · [`docs/PLAN.md`](docs/PLAN.md) ·
mechanism PRDs in [`docs/`](docs/).

## Install

Prerequisites:

1. **Python 3.12+** managed by [`uv`](https://docs.astral.sh/uv/) (no pip/venv):
   `brew install uv` / `winget install astral-sh.uv`
2. **A LaTeX distribution** with LuaLaTeX + bibtex:
   - macOS: `brew install --cask basictex`, then `sudo tlmgr install luabidi`
     (or without sudo: `tlmgr init-usertree && tlmgr --usermode install luabidi`)
   - Windows: install [MiKTeX](https://miktex.org) (auto-installs missing packages)
3. **API keys** (see [Configuration](#configuration)).

```bash
git clone https://github.com/swalha1999/PDFfactory.git
cd PDFfactory
uv sync                      # installs everything from the committed uv.lock
cp .env-example .env         # then fill in your keys
```

## Usage

```bash
# Full pipeline: research -> write -> edit -> LaTeX -> compile -> validate
uv run agentscribe --topic "Agentic AI in Production"

# Fast review: stop after the Markdown draft (no LaTeX)
uv run agentscribe --topic "Agentic AI in Production" --markdown-only

# Override config per run
uv run agentscribe --topic "..." --language en --target-pages 12
```

Every run writes to `results/<run-id>/`:

| Artifact | What it is |
|----------|------------|
| `output.pdf` | the typeset document |
| `draft.md`, `main.tex`, `references.bib`, `chart.png` | build inputs |
| `envelope_report.json` / `.md` | C1–C11 technical-envelope verdicts |
| `cost_report.json` / `.md` | tokens, USD, stage timings, cost-at-scale |
| `run.jsonl` | structured log of every event and API call |
| `pass1..4.log`, `bibtex.log` | compiler output per pass |

### Using the SDK directly

```python
from agentscribe.sdk.sdk import AgentScribeSDK

sdk = AgentScribeSDK.from_default_config()
result = sdk.generate_document("Agentic AI in Production")
print(result.pdf_path, result.all_pass, result.cost_usd)
```

The CLI is a logic-free wrapper; everything routes through the SDK
(`generate_document`, `generate_markdown`, `build_latex`, `compile_pdf`,
`validate`).

## Configuration

Secrets come **only** from the environment (`.env`, never committed):

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | yes (default provider) | LLM calls via CrewAI/LiteLLM |
| `SERPER_API_KEY` | yes | research agent's web search |
| `AGENTSCRIBE_WORKER_MODEL` / `AGENTSCRIBE_ENGINEER_MODEL` | no | override the configured models |

Operational policy lives in versioned `config/*.json` (all start at v1.00, checked at startup):

- `setup.json` — language, target pages, compiler (`lualatex`/`xelatex`),
  passes, bib backend, models, sandbox limits, validator thresholds, cover metadata.
- `rate_limits.json` — per-service requests/minute+hour, concurrency,
  retries, overflow-queue depth (enforced by the API gatekeeper).
- `model_prices.json` — $/MTok per model (drives the cost report; no price in code).
- `logging_config.json` — level and secret-redaction keys.

## Architecture (short version)

- **SDK-fronted, layered** — consumers only touch `AgentScribeSDK` (PLAN §5).
- **API gatekeeper** — every LLM/search call passes one chokepoint: sliding-window
  rate limits, FIFO overflow queue with backpressure, retries, per-call token records.
- **Sandboxed generated code** — the matplotlib chart script runs in an isolated
  process with an empty environment after a static AST pre-check; on failure the
  run degrades to a placeholder figure instead of dying.
- **Deterministic envelope** — the LaTeX engine injects any missing graded element
  (table/formula/figure/BiDi/citations), and a validator re-checks all C1–C11 on
  the built PDF; failures trigger a bounded self-correction loop.
- **Observability** — structured JSONL log per run with secret redaction, plus a
  cost report (written even for failed runs).

## Cost (tokens & dollars)

Estimated for one ~15-page run with the default models
(workers: `claude-haiku-4-5`, engineer: `claude-sonnet-4-6`; prices from
`config/model_prices.json`):

| Stage | Model | Input tok | Output tok | USD |
|-------|-------|----------:|-----------:|----:|
| Research + Write + Edit | haiku 4.5 ($1 / $5 per MTok) | ~45,000 | ~20,000 | ~$0.15 |
| LaTeX prep | sonnet 4.6 ($3 / $15 per MTok) | ~20,000 | ~12,000 | ~$0.24 |
| **Total per run** | | **~65,000** | **~32,000** | **≈ $0.39** |

At scale (linear): ~$3.90 / 10 runs, ~$39 / 100 runs. Actuals land in each
run's `cost_report.md`, including a per-model breakdown and projection.
**Optimization notes:** volume prose goes to the cheap worker model; only the
markup-critical stage pays for the stronger model; the gatekeeper's rate
limits cap burst spend; `--markdown-only` skips LaTeX during prompt iteration.

## Development & quality gates

```bash
uv run ruff check . && uv run ruff format --check .   # 0 violations
uv run mypy                                           # strict
uv run pytest --cov                                   # >= 85% (currently ~97%)
uv run python scripts/check_line_limit.py             # every file <= 150 lines
uv run python scripts/secret_scan.py                  # no committed secrets
```

The same gates run in CI on every push. Tests never call live APIs — the crew
is mocked; integration tests that need LuaLaTeX skip automatically where it
is missing.

## Troubleshooting

- ``File `luabidi.sty' not found`` → `tlmgr --usermode install luabidi`
  (after `tlmgr init-usertree`).
- **Hebrew font errors** → set `latex.hebrew_font` in `config/setup.json` to an
  installed Hebrew-capable font (macOS: `Arial Hebrew`; Windows: `David CLM` or `Arial`).
- **`GatekeeperQueueFullError`** → over rate limits; raise the limits in
  `config/rate_limits.json` or rerun later.
- **Validator fails C1 (page count)** → raise `--target-pages` or lower the
  tolerance in `setup.json`.

## License & credits

MIT License. Built by **Mohammed Abad** for *Mass Production of AI Agents*
(Dr. Yoram Segal). Powered by [CrewAI](https://docs.crewai.com),
[matplotlib](https://matplotlib.org), [pypdf](https://pypdf.readthedocs.io),
[pdfplumber](https://github.com/jsvine/pdfplumber),
[structlog](https://www.structlog.org) and a LaTeX toolchain
(LuaLaTeX, polyglossia, TikZ, fancyhdr).
