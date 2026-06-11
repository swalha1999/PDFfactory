"""Centralized API gatekeeper (PRD_api_gatekeeper; PLAN ADR-006).

Every outbound call (LLM, search) passes through ``ApiGatekeeper.execute``:
sliding-window rate limiting, a bounded FIFO overflow queue with
backpressure, retries with exponential backoff, and per-call records that
feed the cost reporter. All limits come from config/rate_limits.json.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from agentscribe.shared.config import Config
from agentscribe.shared.logging_setup import get_logger
from agentscribe.shared.rate_limit import (
    CallRecord,
    GatekeeperQueueFullError,
    GatekeeperRetryExhaustedError,
    ServiceState,
    is_transient,
)


class ApiGatekeeper:
    """Single chokepoint for all external API calls (R1)."""

    def __init__(
        self,
        config: Config,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._clock = clock
        self._sleep = sleeper
        self._states: dict[str, ServiceState] = {}
        self._lock = threading.Lock()
        self.records: list[CallRecord] = []

    def _state(self, service: str) -> ServiceState:
        with self._lock:
            if service not in self._states:
                self._states[service] = ServiceState(self._config.service_limits(service))
            return self._states[service]

    def _admit(self, state: ServiceState, service: str) -> float:
        """Wait for window capacity in FIFO order; backpressure when queue is full."""
        max_depth = int(self._config.queue_config["max_depth"])
        with self._lock:
            if state.waiting >= max_depth:
                msg = f"{service}: overflow queue at max_depth={max_depth}"
                raise GatekeeperQueueFullError(msg)
            state.waiting += 1
        enqueued = self._clock()
        try:
            with state.admission:  # admits one caller at a time, in arrival order (R3)
                delay = state.next_free_in(self._clock())
                while delay > 0:
                    self._sleep(delay)
                    delay = state.next_free_in(self._clock())
                state.record(self._clock())
        finally:
            with self._lock:
                state.waiting -= 1
        return (self._clock() - enqueued) * 1000

    def execute(
        self,
        service: str,
        call: Callable[..., Any],
        *args: Any,
        model: str | None = None,
        usage_extractor: Callable[[Any], dict[str, int]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Rate-limit, queue, retry, and log one external call (R2-R5)."""
        state = self._state(service)
        record = CallRecord(service=service, started_at=self._clock(), model=model)
        record.queued_ms = self._admit(state, service)
        retries = int(state.limits["max_retries"])
        backoff = float(state.limits["retry_after_seconds"])
        with state.semaphore:
            start = self._clock()
            for attempt in range(1, retries + 2):
                record.attempt = attempt
                try:
                    result = call(*args, **kwargs)
                except Exception as exc:
                    if not is_transient(exc) or attempt > retries:
                        self._finish(record, start, "failed", error=str(exc))
                        if is_transient(exc):
                            raise GatekeeperRetryExhaustedError(str(exc)) from exc
                        raise
                    self._sleep(backoff * 2 ** (attempt - 1))
                    continue
                if usage_extractor is not None:
                    record.tokens = usage_extractor(result)
                self._finish(record, start, "success" if attempt == 1 else "retried")
                return result
        return None  # pragma: no cover - loop always returns or raises

    def _finish(self, record: CallRecord, start: float, outcome: str, **extra: Any) -> None:
        record.latency_ms = (self._clock() - start) * 1000
        record.outcome = outcome
        self.records.append(record)
        get_logger(service=record.service).info("api_call", **vars(record), **extra)

    def get_queue_status(self) -> dict[str, Any]:
        """Queue depth and remaining quota per service (R7)."""
        now = self._clock()
        status: dict[str, Any] = {"total_calls": len(self.records)}
        with self._lock:
            for name, state in self._states.items():
                state.prune(now)
                status[name] = {
                    "waiting": state.waiting,
                    "remaining_minute": state.limits["requests_per_minute"] - len(state.minute),
                    "remaining_hour": state.limits["requests_per_hour"] - len(state.hour),
                }
        return status
