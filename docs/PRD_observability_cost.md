# PRD (Mechanism) — Observability, Logging & Cost Accounting

**Parent:** [`PRD.md`](PRD.md) · **Architecture:** [`PLAN.md`](PLAN.md) (§8)
**Version:** 1.00 · **Last updated:** 2026-06-10

Dedicated PRD for the cross-cutting layer every other service depends on:
structured logging, per-run artifacts, and the token/cost report ("Spec Sheet").

---

## 1. Theoretical Background

The lecture's production principles (L06 §9) require **measurement**: "anyone
who wants to be professional produces a Spec Sheet: response times, memory use,
expected token counts — these are the questions that turn a system into a
serious one," and "the more permissions an agent gets, the more important the
observability layer — more than the model itself." Monitoring reports and
incident logging are a requirement before going to production (§8). For
AgentScribe this means: every run is reconstructible from its artifacts, every
external call is visible, and every run ends with an explicit cost figure —
product goal G6 (*cost transparency: always*).

## 2. Inputs / Outputs / Setup

### 2.1 Input
- Log events emitted by all services (crew, gatekeeper, latex, sandbox,
  validator) through one `shared/logging_setup.py` factory.
- `CallRecord`s from the gatekeeper (tokens per LLM call).
- Model price table from `config/model_prices.json` (versioned, starts 1.00).

### 2.2 Output — per run, under `results/<run-id>/`
- `run.log.jsonl` — structured JSON log (one event per line: `ts`, `run_id`,
  `service`, `event`, `level`, payload).
- Console output — human-readable pretty rendering of the same events.
- `cost_report.json` + a Markdown table:

```json
{
  "run_id": "…",
  "by_model": [
    { "model": "gpt-4o-mini", "calls": 12, "input_tokens": 0,
      "output_tokens": 0, "usd": 0.0 }
  ],
  "search_calls": 4,
  "total_usd": 0.0,
  "duration_s": 0,
  "stage_timings_s": { "research": 0, "write": 0, "edit": 0,
                       "latex": 0, "compile": 0, "validate": 0 }
}
```

### 2.3 Setup parameters (config)
- `config/logging_config.json`: level, sinks, redaction patterns — versioned.
- `config/model_prices.json`: `{ "model": { "input_per_mtok": $, "output_per_mtok": $ } }`.

## 3. Specific Requirements
- **R1 — Single logging factory:** all modules get loggers from
  `shared/logging_setup.py`; no `print()` in shipped code (ruff `T20` enforced).
- **R2 — `run_id` everywhere:** generated once per SDK call; bound to every log
  event so one `grep run_id` reconstructs a run.
- **R3 — Secret redaction:** a log filter redacts values of keys matching
  `*_API_KEY`/`token`/`secret` patterns before any sink writes them.
- **R4 — Stage telemetry:** SDK emits `stage_started`/`stage_finished` events
  with durations for each pipeline stage (feeds `stage_timings_s`).
- **R5 — Cost computation:** `shared/cost.py` aggregates gatekeeper
  `CallRecord`s, multiplies by `model_prices.json` (price table is config —
  **no price constant in code**), and writes the report at run end, **including
  on failure** (a failed run still reports what it spent).
- **R6 — Scalability note in report:** the Markdown report includes the
  projected cost per N runs (linear extrapolation) — the "what does this cost
  at scale" answer the guidelines ask for.
- **R7 — Compiler/sandbox logs retained:** every external process's output is
  persisted per run (`pass1.log`, `biber.log`, sandbox stdout/stderr tails).

## 4. Performance Metrics
- Logging overhead < 2% of run wall-clock (sampled).
- `cost_report.json` present for 100% of runs, including failed ones (tested).
- Reported totals match the mocked usage figures exactly in tests (no drift
  between gatekeeper accounting and the report).

## 5. Constraints & Alternatives
- **Constraint:** prices change; that is why the price table is a versioned
  config file, not code, and the report names the price-table version used.
- **Alternative — third-party tracing (LangSmith/AgentOps):** valuable but
  external SaaS; rejected for the submission (offline-reproducible grading),
  noted as future work in PRD §12-equivalent.
- **Alternative — plain-text logs:** rejected; JSONL is machine-parseable for
  the results-analysis notebook (guidelines §9) and the pretty console renderer
  keeps it human-friendly.

## 6. Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| OB-1 | Full mocked run | `run.log.jsonl` + `cost_report.json` written; totals match mock usage |
| OB-2 | Failed run mid-pipeline | Cost report still written with partial totals; failure event logged |
| OB-3 | API key appears in an event payload | Redacted in every sink |
| OB-4 | Unknown model in usage record | Report flags `unknown_price`; run does not crash |
| OB-5 | Stage timing events | All six stages present with positive durations |
| OB-6 | `print()` in source tree | ruff gate fails (T20) |
