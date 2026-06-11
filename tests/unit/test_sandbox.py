"""Tests for shared/sandbox*.py - PRD_sandbox_runner scenarios SB-1..SB-8."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentscribe.shared.sandbox import run_in_sandbox
from agentscribe.shared.sandbox_precheck import precheck_script

ALLOWED = ["matplotlib", "numpy", "math", "random"]


def run(script: str, out: Path, expected: list[str], **kw: int) -> object:
    return run_in_sandbox(script, expected, out, allowed_imports=ALLOWED, **kw)


def test_sb1_valid_script_outputs_collected_and_hashed(tmp_path: Path) -> None:
    script = 'open("chart.png", "wb").write(b"PNGDATA")\n'
    result = run_in_sandbox(script, ["chart.png"], tmp_path, allowed_imports=ALLOWED)
    assert result.status == "success"
    assert (tmp_path / "chart.png").read_bytes() == b"PNGDATA"
    assert result.manifest[0]["file"] == "chart.png"
    assert result.manifest[0]["source"] == "sandbox"
    assert len(result.manifest[0]["sha256"]) == 64


def test_sb2_script_exception_reports_error(tmp_path: Path) -> None:
    result = run_in_sandbox('raise RuntimeError("boom")', [], tmp_path, allowed_imports=ALLOWED)
    assert result.status == "error"
    assert "boom" in result.stderr_tail


def test_sb3_environ_access_rejected_by_precheck(tmp_path: Path) -> None:
    result = run_in_sandbox(
        "import os\nprint(os.environ)", ["x"], tmp_path, allowed_imports=ALLOWED
    )
    assert result.status == "rejected"
    assert any("forbidden import 'os'" in v for v in result.violations)


def test_sb4_subprocess_and_socket_rejected() -> None:
    for module in ("subprocess", "socket"):
        check = precheck_script(f"import {module}", ALLOWED)
        assert not check.ok


def test_sb5_open_outside_workdir_rejected() -> None:
    for path in ("/etc/passwd", "../escape.txt", "~/x"):
        check = precheck_script(f'open("{path}")', ALLOWED)
        assert not check.ok, path
    assert precheck_script('open("chart.png", "wb")', ALLOWED).ok


def test_sb6_infinite_loop_killed_at_timeout(tmp_path: Path) -> None:
    result = run_in_sandbox(
        "while True:\n    pass", [], tmp_path, allowed_imports=ALLOWED, timeout_s=1
    )
    assert result.status == "timeout"


def test_sb7_output_over_size_cap_fails(tmp_path: Path) -> None:
    script = 'open("big.bin", "wb").write(b"x" * 2_000_000)\n'
    result = run_in_sandbox(script, ["big.bin"], tmp_path, allowed_imports=ALLOWED, max_output_mb=1)
    assert result.status == "output_missing"
    assert result.produced_files == []


def test_sb8_no_secrets_visible_inside_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The precheck rightly forbids `import os`, so the env probe bypasses it
    # to verify the *runtime* boundary: the child process env carries no keys.
    from agentscribe.shared import sandbox
    from agentscribe.shared.sandbox_precheck import PrecheckResult

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setattr(sandbox, "precheck_script", lambda s, a: PrecheckResult(ok=True))
    script = 'import os\nopen("env.txt", "w").write(",".join(sorted(os.environ)))\n'
    result = run_in_sandbox(script, ["env.txt"], tmp_path, allowed_imports=ALLOWED)
    assert result.status == "success"
    env_keys = (tmp_path / "env.txt").read_text()
    assert "ANTHROPIC_API_KEY" not in env_keys
    assert "SERPER_API_KEY" not in env_keys


def test_missing_expected_output(tmp_path: Path) -> None:
    result = run_in_sandbox("x = 1", ["never.png"], tmp_path, allowed_imports=ALLOWED)
    assert result.status == "output_missing"


def test_forbidden_calls_and_syntax_error() -> None:
    assert not precheck_script('eval("1+1")', ALLOWED).ok
    assert not precheck_script("import numpy as np\nx(", ALLOWED).ok
    assert not precheck_script("import pandas", ALLOWED).ok  # not in allowlist
    assert precheck_script("import math\nprint(math.pi)", ALLOWED).ok
