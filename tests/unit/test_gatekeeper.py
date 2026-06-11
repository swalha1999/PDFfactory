"""Tests for shared/gatekeeper.py - PRD_api_gatekeeper scenarios GK-1..GK-7."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from agentscribe.shared.config import Config
from agentscribe.shared.gatekeeper import ApiGatekeeper
from agentscribe.shared.rate_limit import (
    GatekeeperQueueFullError,
    GatekeeperRetryExhaustedError,
    TransientApiError,
)


class StubConfig(Config):
    """Config double - limits injected directly, no files read."""

    def __init__(self, limits: dict[str, int], queue: dict[str, Any]) -> None:
        self._limits = limits
        self._queue = queue

    def service_limits(self, service: str) -> dict[str, int]:
        return dict(self._limits)

    @property
    def queue_config(self) -> dict[str, Any]:
        return dict(self._queue)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def make_gatekeeper(
    rpm: int = 5, rph: int = 100, retries: int = 2, max_depth: int = 10
) -> tuple[ApiGatekeeper, FakeClock]:
    clock = FakeClock()
    cfg = StubConfig(
        {
            "requests_per_minute": rpm,
            "requests_per_hour": rph,
            "concurrent_max": 3,
            "retry_after_seconds": 1,
            "max_retries": retries,
        },
        {"max_depth": max_depth, "backpressure": True},
    )
    return ApiGatekeeper(cfg, clock=clock, sleeper=clock.sleep), clock


def test_gk1_call_within_limits_executes_immediately() -> None:
    gk, _ = make_gatekeeper()
    assert gk.execute("llm", lambda x: x * 2, 21) == 42
    record = gk.records[0]
    assert record.outcome == "success"
    assert record.queued_ms == 0
    assert record.attempt == 1


def test_gk2_burst_over_minute_limit_is_queued_not_dropped() -> None:
    gk, clock = make_gatekeeper(rpm=2)
    results = [gk.execute("search", lambda i=i: i) for i in range(3)]
    assert results == [0, 1, 2]  # all complete, FIFO order
    assert gk.records[2].queued_ms > 0  # third call waited for the window
    assert clock.now >= 60  # the fake clock advanced past the window


def test_gk3_queue_full_raises_backpressure() -> None:
    gk, _ = make_gatekeeper(max_depth=1)
    gk._state("llm").waiting = 1  # simulate a full overflow queue
    with pytest.raises(GatekeeperQueueFullError, match="max_depth=1"):
        gk.execute("llm", lambda: "x")


def test_gk4_transient_error_retried_with_backoff() -> None:
    gk, clock = make_gatekeeper()
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise TransientApiError("HTTP 429")
        return "ok"

    assert gk.execute("llm", flaky) == "ok"
    assert gk.records[0].attempt == 2
    assert gk.records[0].outcome == "retried"
    assert clock.now >= 1  # backoff sleep happened


def test_gk5_permanent_transient_failure_exhausts_retries() -> None:
    gk, _ = make_gatekeeper(retries=2)
    calls = {"n": 0}

    def always_down() -> None:
        calls["n"] += 1
        raise TransientApiError("HTTP 503")

    with pytest.raises(GatekeeperRetryExhaustedError):
        gk.execute("llm", always_down)
    assert calls["n"] == 3  # initial + 2 retries
    assert gk.records[0].outcome == "failed"


def test_non_transient_error_surfaces_immediately() -> None:
    gk, _ = make_gatekeeper()

    def boom() -> None:
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        gk.execute("llm", boom)
    assert gk.records[0].attempt == 1


def test_usage_extractor_records_tokens() -> None:
    gk, _ = make_gatekeeper()
    gk.execute(
        "llm",
        lambda: {"usage": {"input": 100, "output": 50}},
        model="anthropic/claude-haiku-4-5",
        usage_extractor=lambda r: dict(r["usage"]),
    )
    assert gk.records[0].tokens == {"input": 100, "output": 50}
    assert gk.records[0].model == "anthropic/claude-haiku-4-5"


def test_gk6_concurrent_calls_respect_concurrent_max() -> None:
    gk, _ = make_gatekeeper(rpm=100, rph=1000)
    active, peak, lock = [0], [0], threading.Lock()

    def tracked() -> None:
        import time

        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.01)
        with lock:
            active[0] -= 1

    threads = [threading.Thread(target=gk.execute, args=("llm", tracked)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] <= 3  # concurrent_max
    assert len(gk.records) == 8  # 100% of calls logged


def test_queue_status_reports_remaining_quota() -> None:
    gk, _ = make_gatekeeper(rpm=5)
    gk.execute("llm", lambda: 1)
    gk.execute("llm", lambda: 2)
    status = gk.get_queue_status()
    assert status["total_calls"] == 2
    assert status["llm"]["remaining_minute"] == 3
    assert status["llm"]["waiting"] == 0
