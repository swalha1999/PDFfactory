"""Tests for figures.py, engine.py and compiler.py (mocked compile)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentscribe import constants
from agentscribe.services.crew.models import Chapter, MarkdownDraft, RequiredElements
from agentscribe.services.latex import compiler as compiler_mod
from agentscribe.services.latex import engine as engine_mod
from agentscribe.services.latex.compiler import CompileError, compile_pdf
from agentscribe.services.latex.engine import LatexEngine, ensure_elements
from agentscribe.services.latex.figures import build_chart_script, generate_chart
from agentscribe.shared.config import Config
from agentscribe.shared.sandbox import SandboxResult
from agentscribe.shared.sandbox_precheck import precheck_script


def bare_draft() -> MarkdownDraft:
    return MarkdownDraft(
        title="Topic",
        chapters=[Chapter(heading="Intro", body_markdown="Plain text only.")],
        required_elements=RequiredElements(),
    )


def test_chart_script_is_deterministic_and_precheck_clean() -> None:
    script_a = build_chart_script("Agentic AI")
    assert script_a == build_chart_script("Agentic AI")
    assert script_a != build_chart_script("Other Topic")
    assert precheck_script(script_a, ["matplotlib", "numpy", "math", "random"]).ok


def test_generate_chart_degrades_to_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def failing_sandbox(*args: object, **kwargs: object) -> SandboxResult:
        calls["n"] += 1
        return SandboxResult(status="error", stderr_tail="boom")

    monkeypatch.setattr("agentscribe.services.latex.figures.run_in_sandbox", failing_sandbox)
    path, degraded, _ = generate_chart(Config(), "T", tmp_path)
    assert calls["n"] == 2  # one retry (sandbox PRD R6)
    assert degraded is True
    assert path.is_file()  # placeholder copied


def test_ensure_elements_injects_all_missing() -> None:
    markdown = ensure_elements(bare_draft(), ["k1", "k2"])
    assert "|---" in markdown or "|--------" in markdown  # table
    assert "$$" in markdown  # formula
    assert "![FIGURE:" in markdown  # figure
    assert "Hebrew Summary" in markdown  # BiDi chapter
    assert "[@k1]" in markdown and "[@k2]" in markdown  # citations


def test_ensure_elements_keeps_existing_without_duplicates() -> None:
    body = "| A | B |\n|---|---|\n| 1 | 2 |\n\n$$x$$\n\n![FIGURE: c](chart.png)\n\nשלום [@a] [@b]"
    draft = MarkdownDraft(
        title="T",
        chapters=[Chapter(heading="Full", body_markdown=body)],
        required_elements=RequiredElements(),
    )
    markdown = ensure_elements(draft, ["k1", "k2"])
    assert "Key Comparisons" not in markdown
    assert "Mathematical Perspective" not in markdown
    assert markdown.count("![FIGURE:") == 1


def test_engine_build_writes_tex_bib_and_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_chart(
        config: Config, topic: str, run_dir: Path, spec: object = None
    ) -> tuple[Path, bool, SandboxResult]:
        path = run_dir / constants.FIGURE_IMAGE_NAME
        path.write_bytes(b"png")
        return path, False, SandboxResult(status="success", manifest=[{"file": "chart.png"}])

    monkeypatch.setattr(engine_mod, "generate_chart", fake_chart)
    artifacts = LatexEngine(Config()).build(bare_draft(), tmp_path, "2026-06-11")
    tex = artifacts.tex_path.read_text()
    assert artifacts.tex_path.name == constants.MAIN_TEX_NAME
    assert r"\begin{tikzpicture}" in tex  # R11
    assert r"\texthebrew" in tex  # C10
    assert r"\begin{equation}" in tex  # C9
    assert r"\begin{tabularx}" in tex  # C8
    assert r"\cite{" in tex  # C11
    assert "@misc{" in artifacts.bib_path.read_text()
    assert artifacts.figure_paths[0].is_file()
    assert artifacts.degraded_figure is False


def test_compiler_missing_binary_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agentscribe.services.latex.compiler.shutil.which", lambda name: None)
    with pytest.raises(CompileError, match="not found"):
        compile_pdf(Config(), tmp_path)


def test_compiler_pass_sequence_and_rename(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_run(cmd: list[str], run_dir: Path, log_name: str) -> int:
        calls.append(" ".join(cmd))
        (run_dir / log_name).write_text("ok")
        if log_name == "pass4.log":
            (run_dir / "main.pdf").write_bytes(b"%PDF-1.5")
        return 0

    monkeypatch.setattr(
        "agentscribe.services.latex.compiler.shutil.which", lambda name: "/usr/bin/" + name
    )
    monkeypatch.setattr(compiler_mod, "_run", fake_run)
    pdf, logs = compile_pdf(Config(), tmp_path)
    assert pdf.name == constants.OUTPUT_PDF_NAME and pdf.is_file()
    assert len([c for c in calls if "xelatex" in c]) == 4
    assert any("bibtex" in c for c in calls)
    assert logs == ["pass1.log", "bibtex.log", "pass2.log", "pass3.log", "pass4.log"]


def test_compiler_failure_surfaces_log_tail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(cmd: list[str], run_dir: Path, log_name: str) -> int:
        (run_dir / log_name).write_text("! Undefined control sequence")
        return 1

    monkeypatch.setattr(
        "agentscribe.services.latex.compiler.shutil.which", lambda name: "/usr/bin/" + name
    )
    monkeypatch.setattr(compiler_mod, "_run", fake_run)
    with pytest.raises(CompileError, match="Undefined control sequence"):
        compile_pdf(Config(), tmp_path)


def test_chart_spec_drives_script_with_fallback() -> None:
    from agentscribe.services.crew.models import ChartSpec

    spec = ChartSpec(
        title="AI adoption by year",
        x_label="Year",
        y_label="Percent",
        labels=["2024", "2025", "2026"],
        values=[12.0, 31.5, 55.0],
    )
    script = build_chart_script("T", spec)
    assert "AI adoption by year" in script
    assert "[12.0, 31.5, 55.0]" in script
    assert precheck_script(script, ["matplotlib", "numpy", "math", "random"]).ok
    # unusable specs fall back to the deterministic chart
    bad = ChartSpec(title="x", labels=["a"], values=[1.0, 2.0])
    assert not bad.usable()
    assert "Key dimensions of" in build_chart_script("T", bad)
    assert "Key dimensions of" in build_chart_script("T", None)


def test_chart_kinds_render_and_pass_precheck() -> None:
    from agentscribe.services.crew.models import ChartSpec

    allowed = ["matplotlib", "numpy", "math", "random"]
    for kind in ("bar", "barh", "line", "pie"):
        spec = ChartSpec(kind=kind, title="T", labels=["a", "b", "c"], values=[1.0, 2.0, 3.0])
        script = build_chart_script("X", spec)
        assert precheck_script(script, allowed).ok, kind
    assert "ax.pie" in build_chart_script(
        "X", ChartSpec(kind="pie", title="T", labels=["a", "b"], values=[1.0, 2.0])
    )
    # pie with non-positive values is unusable -> falls back
    bad_pie = ChartSpec(kind="pie", title="T", labels=["a", "b"], values=[1.0, -2.0])
    assert not bad_pie.usable()


def test_diagram_spec_renders_tikz_and_falls_back() -> None:
    from agentscribe.services.crew.models import DiagramSpec
    from agentscribe.services.latex.diagram import render_diagram

    spec = DiagramSpec(
        caption="CI/CD flow with 100% AI & review",
        nodes=["Commit", "AI Review", "Tests", "Deploy"],
        edges=[(0, 1), (1, 2), (2, 3)],
    )
    assert spec.usable()
    tex = render_diagram(spec)
    assert tex.count(r"\node[block") == 4
    assert r"\draw[arrow] (n0) -- (n1);" in tex
    assert r"100\% AI \&" in tex  # caption escaped
    assert not DiagramSpec(caption="x", nodes=["a", "b"], edges=[(0, 1)]).usable()
    assert not DiagramSpec(caption="x", nodes=["a", "b", "c"], edges=[(0, 9), (1, 2)]).usable()
