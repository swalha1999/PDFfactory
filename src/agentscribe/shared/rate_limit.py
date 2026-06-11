"""Rate-limit primitives for the API gatekeeper (PRD_api_gatekeeper R2-R4).

Sliding minute/hour windows, the per-service state (windows + concurrency
semaphore + queue counter), typed gatekeeper errors, and the CallRecord
emitted for every external call.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class GatekeeperQueueFullError(RuntimeError):
    """Overflow queue is at max_depth - backpressure instead of buffering (R3)."""


class GatekeeperRetryExhaustedError(RuntimeError):
    """A transient failure persisted past max_retries (R4)."""


class TransientApiError(RuntimeError):
    """Marker for retryable errors raised by wrapped callables."""


def is_transient(exc: BaseException) -> bool:
    """Retryable: timeouts, connection drops, HTTP 429/5xx (R4)."""
    if isinstance(exc, TransientApiError | TimeoutError | ConnectionError):
        return True
    status = getattr(exc, "status_code", None)
    return status in TRANSIENT_STATUS_CODES


@dataclass
class CallRecord:
    """Observability record for one external call (PRD §2.2)."""

    service: str
    started_at: float
    latency_ms: float = 0.0
    queued_ms: float = 0.0
    attempt: int = 1
    tokens: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})
    model: str | None = None
    outcome: str = "success"


class ServiceState:
    """Sliding windows + concurrency semaphore + queue counter for one service."""

    def __init__(self, limits: dict[str, int]) -> None:
        self.limits = limits
        self.minute: deque[float] = deque()
        self.hour: deque[float] = deque()
        self.admission = threading.Lock()
        self.semaphore = threading.Semaphore(limits["concurrent_max"])
        self.waiting = 0

    def prune(self, now: float) -> None:
        while self.minute and now - self.minute[0] >= 60:
            self.minute.popleft()
        while self.hour and now - self.hour[0] >= 3600:
            self.hour.popleft()

    def next_free_in(self, now: float) -> float:
        """Seconds until a new call fits both windows (0 when free now)."""
        self.prune(now)
        delays = [0.0]
        if len(self.minute) >= self.limits["requests_per_minute"]:
            delays.append(60 - (now - self.minute[0]))
        if len(self.hour) >= self.limits["requests_per_hour"]:
            delays.append(3600 - (now - self.hour[0]))
        return max(delays)

    def record(self, now: float) -> None:
        self.minute.append(now)
        self.hour.append(now)
