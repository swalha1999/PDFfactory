"""Sandboxed execution of agent-generated Python (PRD_sandbox_runner; ADR-005).

The ``subprocess_isolated`` backend runs the script in a separate process
with a clean environment (no API keys), a private temp workdir, a wall-clock
timeout, and an output-size cap. Only ``expected_outputs`` are collected out
of the workdir; everything else is discarded (R3-R5).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from agentscribe.shared.logging_setup import get_logger
from agentscribe.shared.sandbox_precheck import precheck_script

TAIL_CHARS = 2000
SCRIPT_NAME = "generated_script.py"


@dataclass
class SandboxResult:
    """Outcome contract consumed by figures.py and the envelope validator."""

    status: str  # success | rejected | timeout | error | output_missing
    produced_files: list[Path] = field(default_factory=list)
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_ms: float = 0.0
    violations: list[str] = field(default_factory=list)
    manifest: list[dict[str, str]] = field(default_factory=list)


def _clean_env(workdir: Path) -> dict[str, str]:
    """Empty environment: no keys leak into generated code (R3)."""
    return {"HOME": str(workdir), "MPLBACKEND": "Agg", "PYTHONDONTWRITEBYTECODE": "1"}


def _collect(
    workdir: Path, expected: list[str], output_dir: Path, max_bytes: int, result: SandboxResult
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in expected:
        src = workdir / name
        if not src.is_file():
            result.status = "output_missing"
            result.violations.append(f"expected output not produced: {name}")
            continue
        if src.stat().st_size > max_bytes:
            result.status = "output_missing"
            result.violations.append(f"output exceeds size cap: {name}")
            continue
        data = src.read_bytes()
        dest = output_dir / name
        dest.write_bytes(data)
        result.produced_files.append(dest)
        result.manifest.append(
            {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "source": "sandbox"}
        )


def run_in_sandbox(
    script: str,
    expected_outputs: list[str],
    output_dir: Path,
    *,
    allowed_imports: list[str],
    timeout_s: int = 60,
    max_output_mb: int = 10,
) -> SandboxResult:
    """Pre-check then execute the script isolated; collect expected outputs."""
    log = get_logger(service="sandbox")
    script_hash = hashlib.sha256(script.encode()).hexdigest()[:12]
    check = precheck_script(script, allowed_imports)
    if not check.ok:
        log.warning("sandbox_rejected", script_hash=script_hash, violations=check.violations)
        return SandboxResult(status="rejected", violations=check.violations)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="agentscribe-sbx-") as tmp:
        workdir = Path(tmp)
        (workdir / SCRIPT_NAME).write_text(script, encoding="utf-8")
        result = SandboxResult(status="success")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", SCRIPT_NAME],
                cwd=workdir,
                env=_clean_env(workdir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            result.stdout_tail = proc.stdout[-TAIL_CHARS:]
            result.stderr_tail = proc.stderr[-TAIL_CHARS:]
            if proc.returncode != 0:
                result.status = "error"
        except subprocess.TimeoutExpired as exc:
            result.status = "timeout"
            result.stderr_tail = str(exc)[-TAIL_CHARS:]
        result.duration_ms = (time.monotonic() - started) * 1000
        if result.status == "success":
            _collect(workdir, expected_outputs, output_dir, max_output_mb * 1024 * 1024, result)
    log.info(
        "sandbox_run",
        script_hash=script_hash,
        backend="subprocess_isolated",
        status=result.status,
        duration_ms=round(result.duration_ms, 1),
        stdout_tail=result.stdout_tail[-200:],
        stderr_tail=result.stderr_tail[-200:],
    )
    return result
