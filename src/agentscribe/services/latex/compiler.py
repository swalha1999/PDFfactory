"""Multi-pass LaTeX compile orchestrator (latex PRD R10; ADR-004; #25).

Runs ``latex -> bib backend -> latex -> latex`` (compile_passes total LaTeX
passes from config) so citations and cross-references resolve. Every pass's
output is persisted per run (observability PRD R7).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from agentscribe import constants
from agentscribe.shared.config import Config
from agentscribe.shared.logging_setup import get_logger

PASS_TIMEOUT_S = 300
JOBNAME = "main"


class CompileError(RuntimeError):
    """A LaTeX pass failed; carries the log tail for diagnosis."""


def _run(cmd: list[str], run_dir: Path, log_name: str) -> int:
    proc = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True, timeout=PASS_TIMEOUT_S)
    (run_dir / log_name).write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return proc.returncode


def compile_pdf(config: Config, run_dir: Path) -> tuple[Path, list[str]]:
    """Compile main.tex in run_dir; returns (pdf_path, compiler_log_names)."""
    log = get_logger(service="compiler")
    compiler = str(config.compiler.value)
    if shutil.which(compiler) is None:
        raise CompileError(f"{compiler} not found on PATH - install a LaTeX distribution")
    latex_cmd = [compiler, "-interaction=nonstopmode", f"{JOBNAME}.tex"]
    total_passes = max(2, config.compile_passes)
    logs: list[str] = []

    def latex_pass(n: int) -> None:
        log_name = f"pass{n}.log"
        code = _run(latex_cmd, run_dir, log_name)
        logs.append(log_name)
        log.info("latex_pass", n=n, exit_code=code)
        if code != 0:
            tail = (run_dir / log_name).read_text(encoding="utf-8", errors="replace")[-1500:]
            raise CompileError(f"{compiler} pass {n} failed:\n{tail}")

    latex_pass(1)
    backend = str(config.bib_backend.value)
    bib_code = _run([backend, JOBNAME], run_dir, f"{backend}.log")
    logs.append(f"{backend}.log")
    log.info("bib_pass", backend=backend, exit_code=bib_code)
    if bib_code != 0:  # warnings are common; the final pass decides success
        log.warning("bib_backend_nonzero", backend=backend, exit_code=bib_code)
    for n in range(2, total_passes + 1):
        latex_pass(n)
    built = run_dir / f"{JOBNAME}.pdf"
    if not built.is_file():
        raise CompileError("compile finished but main.pdf was not produced")
    pdf_path = run_dir / constants.OUTPUT_PDF_NAME
    shutil.move(str(built), pdf_path)
    log.info("compile_done", pdf=str(pdf_path), passes=total_passes)
    return pdf_path, logs
