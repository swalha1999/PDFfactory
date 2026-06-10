# PRD (Mechanism) — Sandbox Runner (Generated-Code Execution)

**Parent:** [`PRD.md`](PRD.md) · **Architecture:** [`PLAN.md`](PLAN.md) (ADR-005)
**Version:** 1.00 · **Last updated:** 2026-06-10

Dedicated PRD for the component that executes **agent-generated Python**
(the matplotlib chart script required by envelope item C7) in an isolated
sandbox — never on the host.

---

## 1. Theoretical Background

The lecture's agent-security section (L06 §5, §8) is unambiguous: code agents
pass Python between agents because one line of code replaces a hundred words of
JSON — but *"in production, all code execution must pass through a Sandbox."*
Generated code is **untrusted input**. The named attack surface applies
directly to us: **prompt injection** (web-search text steering the writer to
emit malicious code), **tool misuse** (a legitimate "run script" tool used to
delete files), **identity abuse** (a script reading our API keys from the
environment), and **memory poisoning**. The sandbox is the hard boundary that
makes those attacks non-events: the script sees no secrets, no network, no host
filesystem — only its input directory and an output directory for the chart.

## 2. Inputs / Outputs / Setup

### 2.1 Input
- `script: str` — the agent-generated Python (matplotlib) source.
- `expected_outputs: list[str]` — filenames the script must produce
  (e.g. `chart_01.png`).
- `timeout_s` — wall-clock limit from config.

### 2.2 Output — `SandboxResult`
```json
{
  "status": "success | timeout | error | output_missing",
  "produced_files": ["figures/chart_01.png"],
  "stdout_tail": "…", "stderr_tail": "…",
  "duration_ms": 0,
  "manifest_entry": { "file": "chart_01.png", "sha256": "…", "source": "sandbox" }
}
```
The `manifest_entry` is consumed by the envelope validator (its C7 check
asserts the embedded chart came from the sandbox, not from a static asset).

### 2.3 Setup parameters (config, never hard-coded)
- `backend`: `"wsl"` (default on Windows) | `"subprocess_isolated"` (CI/Linux —
  separate process, clean env, restricted cwd) | `"windows_sandbox"`.
- `timeout_s` (default 60), `max_output_mb` (default 10).
- `allowed_imports` allowlist for the static pre-check
  (`matplotlib`, `numpy`, `math`, `random`).

## 3. Specific Requirements
- **R1 — No host execution path exists.** The figures service has no code path
  that `exec()`s or `subprocess`-runs the script outside `shared/sandbox.py`.
- **R2 — Static pre-check before execution:** reject scripts importing outside
  `allowed_imports` or containing `os.environ`, `open()` outside the workdir,
  `subprocess`, `socket`/network use. Rejection is logged with the offending
  line and triggers one regeneration request to the LaTeX agent.
- **R3 — Clean environment:** the sandboxed process receives an **empty
  environment** (no `OPENAI_API_KEY`/`SERPER_API_KEY`/etc.), a private temp
  workdir, and no network (backend-enforced where supported; documented as
  best-effort for `subprocess_isolated`).
- **R4 — Resource limits:** wall-clock `timeout_s` kill, output size cap,
  non-interactive (`matplotlib` `Agg` backend forced).
- **R5 — Output contract:** after the run, exactly the `expected_outputs` are
  collected from the workdir into `results/<run-id>/figures/` and hashed into
  the run manifest; anything else in the workdir is discarded.
- **R6 — Graceful degradation:** on `timeout`/`error`/`output_missing` after
  one regeneration attempt, the pipeline embeds a committed placeholder figure,
  marks C7 "degraded" in the envelope report, and continues — a figure bug must
  not kill the whole run (PRD use-case 5).
- **R7 — Full observability:** every sandbox run logs script hash, backend,
  duration, status, and stdout/stderr tails to the structured log.

## 4. Performance Metrics
- Chart script executes within `timeout_s`; typical run < 10 s.
- 0 secrets observable inside the sandbox (asserted by a test script that
  prints `os.environ` — must come back empty of our keys).
- 100% of malicious fixtures blocked (see SB-3..SB-6).

## 5. Constraints & Alternatives
- **Constraint:** the evaluator runs on Windows; WSL is the recommended backend
  (the lecture recommends WSL since CLI tools work best in Linux). The
  `subprocess_isolated` backend keeps CI and non-Windows dev machines working.
- **Alternative — Docker:** strongest isolation, but adds a heavyweight
  dependency the course environment may not have; backend interface leaves room
  to add it later without engine changes.
- **Alternative — trust the generated code (no sandbox):** rejected outright —
  contradicts ADR-005 and the lecture's security mandate.
- **Alternative — RestrictedPython/AST-only sandboxing:** in-process sandboxes
  are escape-prone; we use process isolation + static pre-check instead.

## 6. Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| SB-1 | Valid matplotlib script | `success`; PNG collected; manifest hashed |
| SB-2 | Script raises an exception | `error`; stderr captured; placeholder used after 1 retry |
| SB-3 | Script reads `os.environ` | Rejected by pre-check; regeneration requested |
| SB-4 | Script imports `subprocess`/`socket` | Rejected by pre-check |
| SB-5 | Script writes outside workdir | Blocked/ignored; only expected outputs collected |
| SB-6 | Infinite loop | Killed at `timeout_s`; `timeout` status |
| SB-7 | Output exceeds `max_output_mb` | Run failed with `output_missing`/size error |
| SB-8 | Env probe script | No project secrets visible inside sandbox |

> Sandbox tests run the `subprocess_isolated` backend with harmless fixture
> scripts; WSL/Windows Sandbox backends get a smoke test guarded by an
> environment marker.
