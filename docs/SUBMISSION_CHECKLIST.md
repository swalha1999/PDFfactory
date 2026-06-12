# Submission Checklist Walkthrough (guidelines §17)

Status as of 2026-06-11. Each item names the evidence in this repository.

## 17.1 Mandatory Structure and Documentation

- [x] **Comprehensive README.md, user-manual grade** — [`README.md`](../README.md): install (uv + LaTeX), usage (CLI + SDK), config reference, architecture, cost table, troubleshooting, license/credits.
- [x] **docs/ with PRD.md, PLAN.md, TODO.md** — [`PRD.md`](PRD.md), [`PLAN.md`](PLAN.md) (C4 + ADR-001…007), [`TODO.md`](TODO.md).
- [x] **Dedicated PRDs per mechanism** — [`PRD_crew_pipeline.md`](PRD_crew_pipeline.md), [`PRD_latex_compiler.md`](PRD_latex_compiler.md), [`PRD_api_gatekeeper.md`](PRD_api_gatekeeper.md), [`PRD_envelope_validator.md`](PRD_envelope_validator.md), [`PRD_sandbox_runner.md`](PRD_sandbox_runner.md), [`PRD_observability_cost.md`](PRD_observability_cost.md).
- [x] **Architecture diagrams** — PLAN §1–§3 (layer diagram, C4 levels 1–3 in mermaid, pipeline sequence diagram); a TikZ block diagram also ships inside every generated PDF.
- [x] **Documented prompt book** — [`prompt_book.md`](prompt_book.md): agent prompts with iteration history + the AI-driven build prompts.

## 17.2 Architecture and Code

- [x] **SDK architecture** — all logic behind `AgentScribeSDK` (`src/agentscribe/sdk/sdk.py`); `main.py` parses args only (verified by `tests/unit/test_cli.py`).
- [x] **OOP, no duplication** — single agent factory, one gatekeeper, one config manager; shared models in `services/crew/models.py`.
- [x] **API gatekeeper for all external calls** — `shared/gatekeeper.py`; enforced by the import-scan fitness test (`tests/unit/test_import_fitness.py`: no HTTP/vendor imports outside `shared/`).
- [x] **Rate limits from config + overflow queue** — `config/rate_limits.json` (v1.00); FIFO queue with backpressure (`GatekeeperQueueFullError`), tested GK-1…GK-7.
- [x] **Files ≤150 lines, comments and docstrings** — `scripts/check_line_limit.py` gate, green in CI.
- [x] **Consistent style, descriptive names** — ruff (incl. naming rules `N`) + mypy strict, 0 violations.

## 17.3 Testing and Quality

- [x] **TDD** — tests landed in the same commit as each module (see git history); every PRD test scenario (GK/SB/CP/LC/EV) maps to a named test.
- [x] **Coverage ≥85%** — `fail_under = 85` in `pyproject.toml`; current ≈97%.
- [x] **Zero ruff violations** — CI gate.
- [x] **Edge cases & error handling** — timeouts, queue overflow, retry exhaustion, sandbox rejection/timeout/size-cap, compiler failure with log tail, malformed crew output, version mismatch, missing/malformed config.
- [x] **Automated test reports** — pytest + coverage in CI on every push (`.github/workflows/ci.yml`).

## 17.4 Configuration and Security

- [x] **Versioned config files** — `config/*.json` all v1.00, checked at startup (`shared/version.py`).
- [x] **`.env-example` with placeholders** — present; secret scan allows only placeholders.
- [x] **No secrets in code** — `scripts/secret_scan.py` gate + log redaction (`shared/logging_setup.py`).
- [x] **`.gitignore` updated** — secrets, results/, caches, LaTeX junk.
- [x] **uv only** — no pip/venv anywhere; `pyproject.toml` + `uv.lock` committed.

## 17.5 Research and Visualization

- [x] **Systematic experiments** — `notebooks/results_analysis.ipynb` (executed): compile-pass sensitivity (real LaTeX experiment), cost vs pages × model pairing, figure determinism.
- [x] **Sensitivity analysis with charts** — same notebook, three executed charts.
- [x] **Token cost analysis + optimization** — README cost table + per-run `cost_report.md` with at-scale projection; optimization notes documented.
- [x] **Screenshots of CLI states / sample PDF pages** — page screenshots and CLI captures in each of [`assets/sample_run_1..4/`](../assets/sample_run_1/) (see the sample-runs table below).

## 17.6 Extensibility and Standards

- [x] **Extension points** — provider swap via config strings (LiteLLM), compiler/bib-backend switches, sandbox backend interface, GUI/REST can mount the SDK (PLAN §1).
- [x] **Professional package layout** — `src/agentscribe/{sdk,services,shared}` with `__init__.py` everywhere; console script `agentscribe`.
- [x] **Parallel processing with thread safety** — gatekeeper windows/semaphore/queue are thread-safe (tested with 8 concurrent threads, GK-6).
- [x] **Building blocks** — every mechanism is an independently testable module.
- [x] **ISO/IEC 25010 mapping** — PRD §4.2.
- [x] **Clean git history, license, attribution** — small per-milestone commits closing issues; MIT license + credits in README.

## Live sample runs — four committed topics

All four samples generated end-to-end with live Anthropic + Serper APIs,
**Sonnet for every agent**, each passing **all 11 envelope checks**, each
with 2-3 article-driven charts (bar/barh/line/pie) and a TikZ flow diagram:

| Sample | Topic | Pages | Cost |
|--------|-------|------:|-----:|
| [`assets/sample_run_1/`](../assets/sample_run_1/) | Multi-Agent Systems in Modern Software Engineering | 19 | $0.72 |
| [`assets/sample_run_2/`](../assets/sample_run_2/) | Agentic Coding: How Autonomous AI Agents Are Reshaping Software Development | 17 | $0.69 |
| [`assets/sample_run_3/`](../assets/sample_run_3/) | From Coder to Orchestrator: The Changing Role of the Software Engineer | 18 | $0.63 |
| [`assets/sample_run_4/`](../assets/sample_run_4/) | AI-Driven Testing and Code Review: Quality Assurance in the Agentic Era | 18 | $0.68 |

Each directory holds `output.pdf`, envelope + cost reports, the draft,
the CLI capture, and page screenshots (cover, charts, Hebrew BiDi
chapter, diagram). Every checklist item is satisfied.
