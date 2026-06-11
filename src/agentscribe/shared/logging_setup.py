"""Structured logging factory (PRD_observability_cost R1-R3).

One JSONL file per run + pretty console output, with secret redaction
applied before any sink writes an event. All modules obtain loggers here;
``print()`` in shipped code is banned (ruff T20).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TextIO

import structlog

REDACTED = "***REDACTED***"
_SECRET_KEY_PATTERN = re.compile(
    r"(api[-_]?key|secret|authorization|password|(^|[-_])token$)", re.I
)


def _looks_secret(key: str, extra_keys: list[str]) -> bool:
    lowered = key.lower()
    return bool(_SECRET_KEY_PATTERN.search(lowered)) or lowered in extra_keys


def make_redactor(extra_keys: list[str] | None = None) -> Any:
    """Build a structlog processor that redacts secret-looking values (R3)."""
    extras = [k.lower() for k in (extra_keys or [])]

    def _redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: REDACTED if _looks_secret(str(k), extras) else _redact(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [_redact(v) for v in value]
        return value

    def processor(logger: object, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = _redact(dict(event_dict))
        return redacted

    return processor


class JsonlWriter:
    """Tee processor: append every event as one JSON line to the run log (R2)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._stream: TextIO = path.open("a", encoding="utf-8")

    def __call__(self, logger: object, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        self._stream.write(json.dumps(event_dict, default=str, ensure_ascii=False) + "\n")
        self._stream.flush()
        return event_dict

    def close(self) -> None:
        self._stream.close()


def setup_run_logging(
    run_id: str,
    log_file: Path,
    *,
    level: str = "INFO",
    redact_keys: list[str] | None = None,
    console: bool = True,
) -> structlog.stdlib.BoundLogger:
    """Configure structlog for one run and return the bound root logger.

    Every event carries ``run_id`` so a single grep reconstructs the run (R2).
    """
    writer = JsonlWriter(log_file)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        make_redactor(redact_keys),
        writer,
    ]
    if console:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id)
    logger: structlog.stdlib.BoundLogger = structlog.get_logger()
    return logger


def get_logger(**bind: Any) -> structlog.stdlib.BoundLogger:
    """Return the current structlog logger, optionally binding extra context."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger()
    return logger.bind(**bind) if bind else logger
