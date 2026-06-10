# PRD (Mechanism) — API Gatekeeper

**Parent:** [`PRD.md`](PRD.md) · **Architecture:** [`PLAN.md`](PLAN.md) (ADR-006)
**Version:** 1.00 · **Last updated:** 2026-06-10

Dedicated PRD for the single chokepoint through which **every** outbound API
call (LLM provider, web search) passes: rate limiting, FIFO overflow queue,
retries, and per-call observability/token accounting.

---

## 1. Theoretical Background

A production agent system is graded on its ability "to repeat, monitor, fix and
adjust over time" (L06 §6). Uncontrolled API calls are the main way an agent
pipeline stops being repeatable: a burst of search calls hits a vendor rate
limit and the run crashes non-deterministically; costs are invisible until the
bill arrives. The gatekeeper turns external calls into a **managed resource**:
limits come from versioned config (never hard-coded), excess calls wait in a
bounded FIFO queue instead of failing, every call is logged with latency and
token counts, and transient failures retry with backoff. This is the same
"centralized gatekeeper" pattern mandated by the submission guidelines (§5) and
proven in our previous project (`agent_debate`).

## 2. Inputs / Outputs / Setup

### 2.1 Input
- An `ApiCall` descriptor: `service` (`"llm" | "search" | "default"`), the
  callable, args/kwargs, and an optional `priority` (reserved, FIFO for now).

### 2.2 Output
- The wrapped call's return value, or a typed error after retries are
  exhausted (`GatekeeperTimeout`, `GatekeeperQueueFull`, `GatekeeperRetryExhausted`).
- A `CallRecord` emitted to the logger/cost reporter per call:

```json
{
  "service": "llm", "started_at": "...", "latency_ms": 0,
  "attempt": 1, "queued_ms": 0,
  "tokens": { "input": 0, "output": 0 },
  "outcome": "success | retried | failed"
}
```

### 2.3 Setup parameters — `config/rate_limits.json` (versioned, starts 1.00)
Per-service: `requests_per_minute`, `requests_per_hour`, `concurrent_max`,
`retry_after_seconds`, `max_retries`. Queue: `max_depth`, `backpressure`.
See PLAN §6.3 for the committed schema. **No limit value appears in code.**

## 3. Specific Requirements
- **R1 — Single chokepoint:** no module other than `shared/gatekeeper.py` may
  import an HTTP client / vendor SDK for LLM or search. Enforced by a unit test
  that scans imports (cheap architectural fitness function).
- **R2 — Sliding-window rate limiting** per service (minute + hour windows),
  plus a `concurrent_max` semaphore.
- **R3 — FIFO overflow queue:** when a window is exhausted the call waits in a
  bounded queue (`max_depth`); when the queue is full, fail fast with
  `GatekeeperQueueFull` (backpressure) rather than buffering unboundedly.
- **R4 — Retries with exponential backoff** on transient errors (HTTP 429/5xx,
  timeouts), capped at `max_retries`; non-transient errors surface immediately.
- **R5 — Token & cost accounting:** every LLM `CallRecord` carries token usage
  (from the CrewAI/LiteLLM usage callback) and is forwarded to `shared/cost.py`.
- **R6 — Thread safety:** crew tools may call concurrently; windows, semaphore
  and queue must be thread-safe.
- **R7 — Status introspection:** `get_queue_status()` returns queue depth,
  per-service remaining quota, and totals — surfaced in the run report.
- **R8 — CrewAI integration:** the search tool handed to agents is a thin
  `crewai` tool wrapper whose body is `gatekeeper.execute(...)`; the LLM is
  routed via CrewAI's LiteLLM layer with usage callbacks captured (the
  gatekeeper still meters and records these calls).

## 4. Performance Metrics
- Overhead per call ≤ 5 ms (excluding queue wait) — measured in tests.
- 0 dropped calls in a run that exceeds the per-minute limit (CP-3 in the crew
  PRD): all overflow is queued and eventually executed or reported.
- 100% of external calls present in the structured log (validated in the
  integration test by comparing mock-call count to log-record count).

## 5. Constraints & Alternatives
- **Constraint:** limits must be conservative enough for the evaluator's free-tier
  keys; defaults in `rate_limits.json` reflect that.
- **Alternative — vendor SDK built-in retry:** rejected as the only mechanism —
  it is per-vendor, invisible to our logs, and bypasses queueing/metering.
- **Alternative — token-bucket library (e.g. `limits`):** acceptable
  implementation detail, but the window/queue policy and config schema are ours;
  we keep the dependency surface minimal and the logic testable.

## 6. Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| GK-1 | Calls within limits | Executed immediately; `CallRecord` logged |
| GK-2 | Burst over `requests_per_minute` | Excess queued FIFO; all complete; `queued_ms > 0` |
| GK-3 | Queue at `max_depth` | `GatekeeperQueueFull` raised; pipeline degrades gracefully |
| GK-4 | Transient 429 then success | One retry with backoff; `attempt = 2`; success |
| GK-5 | Permanent failure | Retries capped; `GatekeeperRetryExhausted`; logged |
| GK-6 | Concurrent calls from N threads | No race; `concurrent_max` respected |
| GK-7 | Import scan | No module outside `shared/` imports vendor HTTP clients |

> All tests use mocked callables and a fake clock — no live API calls
> (guidelines §6.1 rule 7).
