"""Static pre-check for agent-generated Python (PRD_sandbox_runner R2).

Rejects scripts before execution when they import outside the allowlist or
touch dangerous surfaces (environment, subprocesses, sockets, file paths
outside the workdir). Purely AST-based - the script is never imported.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

FORBIDDEN_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "ctypes",
    "importlib",
    "urllib",
    "http",
    "requests",
    "pathlib",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint", "input"}


@dataclass
class PrecheckResult:
    """Outcome of the static scan; violations carry line numbers for the log."""

    ok: bool = True
    violations: list[str] = field(default_factory=list)

    def add(self, lineno: int, message: str) -> None:
        self.ok = False
        self.violations.append(f"line {lineno}: {message}")


def _check_import(result: PrecheckResult, lineno: int, module: str, allowed: set[str]) -> None:
    root = module.split(".")[0]
    if root in FORBIDDEN_MODULES:
        result.add(lineno, f"forbidden import {root!r}")
    elif root not in allowed:
        result.add(lineno, f"import {root!r} not in allowed_imports")


def _check_open_call(result: PrecheckResult, node: ast.Call) -> None:
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        target = node.args[0].value
        if target.startswith(("/", "~", "\\")) or ".." in target or ":" in target:
            result.add(node.lineno, f"open() outside workdir: {target!r}")


def precheck_script(script: str, allowed_imports: list[str]) -> PrecheckResult:
    """Scan the script; ok=False with reasons when anything dangerous appears."""
    result = PrecheckResult()
    allowed = set(allowed_imports)
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        result.add(exc.lineno or 0, f"syntax error: {exc.msg}")
        return result
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import(result, node.lineno, alias.name, allowed)
        elif isinstance(node, ast.ImportFrom):
            _check_import(result, node.lineno, node.module or "", allowed)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in FORBIDDEN_CALLS:
                    result.add(node.lineno, f"forbidden call {func.id}()")
                elif func.id == "open":
                    _check_open_call(result, node)
        elif isinstance(node, ast.Attribute) and node.attr == "environ":
            result.add(node.lineno, "environment access (identity abuse)")
    return result
