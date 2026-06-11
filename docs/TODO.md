# TODO — AgentScribe Task Board

**Companion to:** [`PRD.md`](PRD.md) · [`PLAN.md`](PLAN.md)
**Authors:** Muhammad Swalha & Mohammed Abad (two-person submission)
**Version:** 1.01 · **Last updated:** 2026-06-11

**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done
**Priority:** P0 (blocker) · P1 (core) · P2 (nice-to-have)
**Owner:** two-person project → `@team` everywhere (kept for traceability).

> Update this file as work progresses (guidelines §2.5 step 6). Each task lists its **Definition of Done (DoD)**.

---

## Phase 0 — Documentation & Approval  *(Milestone M0)*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [x] | T0.1 | P0 | Write `docs/PRD.md` | @team | PRD covers overview, goals/KPIs, FR/NFR, assumptions, timeline |
| [x] | T0.2 | P0 | Write `docs/PLAN.md` | @team | C4 diagrams, ADRs, schemas, SDK contracts present |
| [x] | T0.3 | P0 | Write `docs/TODO.md` | @team | Phased tasks with priority, owner, DoD |
| [x] | T0.4 | P0 | Write dedicated PRDs (`PRD_crew_pipeline.md`, `PRD_latex_compiler.md`) | @team | Each has I/O, requirements, success criteria, test scenarios |
| [ ] | T0.5 | P0 | Get document set approved | @team | Stakeholder/self review sign-off before coding |

## Phase 1 — Scaffold & Tooling  *(Milestone M1)*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T1.1 | P0 | Init `uv` project, `pyproject.toml`, `uv.lock` | @team | `uv sync` succeeds; no pip/venv used |
| [ ] | T1.2 | P0 | Package skeleton (`src/agentscribe/**`, `__init__.py` everywhere) | @team | Importable package; `__version__` set |
| [ ] | T1.3 | P0 | Configure ruff + coverage in `pyproject.toml` | @team | `ruff check` clean; `fail_under = 85` set |
| [ ] | T1.4 | P0 | `config/setup.json` + `rate_limits.json` + `logging_config.json` (v1.00) | @team | Loadable, versioned, validated at startup |
| [ ] | T1.5 | P0 | `.env-example`, `.gitignore`, `constants.py`, `shared/version.py` | @team | Secrets only via env; `.env` ignored |
| [ ] | T1.6 | P1 | `shared/config.py` config manager + version check | @team | Reads JSON, exposes typed getters, unit-tested |

## Phase 2 — API Gatekeeper & Sandbox  *(Milestone M1/M2)*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T2.1 | P0 | `shared/gatekeeper.py` — rate limit + retry + log | @team | `execute()` enforces limits; unit-tested with mocks |
| [ ] | T2.2 | P0 | Overflow FIFO queue + backpressure + drain | @team | Integration test: over-limit queues, never crashes |
| [ ] | T2.3 | P0 | `shared/sandbox.py` — run Python in WSL/Windows Sandbox | @team | Generated script runs isolated; host untouched; tested |
| [ ] | T2.4 | P1 | `shared/cost.py` — token/cost reporter | @team | Emits per-run cost JSON (tokens in/out, USD) |

## Phase 3 — CrewAI Pipeline  *(Milestone M2 — see [`PRD_crew_pipeline.md`](PRD_crew_pipeline.md))*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T3.1 | P0 | `crew/agents.py` — researcher/writer/editor/LaTeX agent factory | @team | Each agent has role/goal/backstory/tools; unit-tested |
| [ ] | T3.2 | P0 | `crew/tasks.py` — tasks with `context` chaining | @team | Tasks link via context; expected_output defined |
| [ ] | T3.3 | P0 | `crew/pipeline.py` — assemble Crew, `kickoff(topic)` | @team | Produces structured Markdown draft for a sample topic |
| [ ] | T3.4 | P1 | Route search tool through gatekeeper | @team | No direct API call bypasses gatekeeper (code review) |
| [ ] | T3.5 | P2 | Human-in-the-loop checkpoint (FR-11) | @team | Optional pause after editor stage, config-driven |

## Phase 4 — LaTeX Engine  *(Milestone M3 — see [`PRD_latex_compiler.md`](PRD_latex_compiler.md))*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T4.1 | P0 | `latex/md_to_tex.py` — Markdown → `.tex` | @team | Deterministic conversion; unit-tested on fixtures |
| [ ] | T4.2 | P0 | `latex/templates.py` — cover, TOC, fancyhdr headers/footers | @team | Renders C2–C5 elements |
| [ ] | T4.3 | P0 | `latex/figures.py` — emit + sandbox-run matplotlib chart | @team | Produces image embedded by LaTeX (C7) |
| [ ] | T4.4 | P0 | TikZ block diagram + table + `fancy` formula injection | @team | C6, C8, C9 present; formula is math not flat text |
| [ ] | T4.5 | P0 | Hebrew–English BiDi chapter (LuaLaTeX babel/polyglossia) | @team | C10: RTL↔LTR transitions render correctly |
| [ ] | T4.6 | P0 | `latex/bibliography.py` + `references.bib` | @team | `\cite` entries defined (C11) |
| [ ] | T4.7 | P0 | `latex/compiler.py` — 4-pass `latex→biber→latex→latex` | @team | Clean exit code; citations/cross-refs resolve |

## Phase 5 — Validator & SDK/CLI  *(Milestone M4)*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T5.1 | P0 | `validate/envelope.py` — C1–C11 checks | @team | Returns pass/fail per item; flags overfull boxes, dead links, flat formulas |
| [ ] | T5.2 | P1 | `validate/report.py` — human-readable report | @team | Markdown/JSON report saved per run |
| [ ] | T5.3 | P0 | `sdk/sdk.py` — `AgentScribeSDK` facade | @team | All ops exposed; CLI has zero business logic |
| [ ] | T5.4 | P0 | `main.py` — CLI wrapper (`--topic`, flags) | @team | `uv run agentscribe --topic "X"` → PDF + report |
| [ ] | T5.5 | P1 | Self-correction loop (re-run pass / re-request fancy formula) | @team | Validator failure triggers targeted retry |

## Phase 6 — Quality Gate  *(Milestone M5)*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T6.1 | P0 | Unit tests for every module (happy + error paths) | @team | Each public fn ≥ 1 test; external deps mocked |
| [ ] | T6.2 | P0 | Integration test: end-to-end sample run | @team | Topic → PDF → all envelope checks pass |
| [ ] | T6.3 | P0 | Coverage ≥ 85%, 0 ruff violations | @team | `uv run pytest --cov` green; `ruff check` clean |
| [ ] | T6.4 | P1 | Verify all files ≤ 150 LOC | @team | Automated line-count check passes |

## Phase 7 — Polish, Research & Submit  *(Milestone M6)*
| ✓ | ID | P | Task | Owner | Definition of Done |
|---|----|---|------|-------|--------------------|
| [ ] | T7.1 | P0 | `README.md` — install, usage, examples, config, license/credits + architecture & CrewAI flow diagrams (OOP diagram = bonus) | @team | User-manual grade; diagrams present |
| [ ] | T7.2 | P1 | `docs/prompt_book.md` — significant prompts + iterations | @team | Documents the AI-driven build |
| [ ] | T7.3 | P1 | `notebooks/results_analysis.ipynb` — sensitivity analysis + charts | @team | Parameter exploration (e.g., passes, temperature) with plots |
| [ ] | T7.4 | P1 | Screenshots of CLI states + sample PDF pages → `assets/` | @team | Each key state captured |
| [ ] | T7.5 | P1 | Token cost table + optimization notes | @team | Cost breakdown by model in README |
| [ ] | T7.6 | P0 | Final checklist (guidelines §17) walkthrough | @team | All mandatory items ticked |

---

## Risk register
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BiDi typesetting breaks (C10) | Med | High | Default LuaLaTeX; isolated BiDi test fixture early (T4.5) |
| Citations don't link (C11) | Med | High | Automated 4-pass compile (T4.7); validator catches (T5.1) |
| Flat-text formula (C9) | Med | Med | Validator detect + re-request `fancy formula` (T5.5) |
| Table overflow (C8) | Med | Med | `booktabs`/`tabularx`; validator parses overfull `\hbox` |
| Sandbox unavailable | Low | High | Document WSL setup in README; fail with clear error |
| API rate limits / cost spikes | Med | Med | Gatekeeper queue + cost reporter + budget note |
