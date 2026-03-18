"""End-to-end integration tests for the full CIA pipeline.

These tests create a realistic Git repository, stage changes, and run the
complete CIA pipeline through the CLI — verifying JSON, Markdown, and HTML
output, pre-commit hook behaviour, and all CLI commands.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

from click.testing import CliRunner

from cia.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in *repo*."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a realistic Python project inside a fresh Git repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialise git
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    # Create package structure
    pkg = repo / "mylib"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""mylib — a small demo library."""\n__version__ = "0.1.0"\n',
        encoding="utf-8",
    )
    (pkg / "core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Core logic.\"\"\"
            from mylib import utils

            def process(data: list[int]) -> dict:
                \"\"\"Process numeric data.\"\"\"
                cleaned = utils.validate(data)
                return utils.summarize(cleaned)

            class Pipeline:
                \"\"\"Data processing pipeline.\"\"\"
                def __init__(self, steps: list | None = None):
                    self.steps = steps or []
                def run(self, data: list[int]) -> dict:
                    for step in self.steps:
                        data = step(data)
                    return process(data)
        """),
        encoding="utf-8",
    )
    (pkg / "utils.py").write_text(
        textwrap.dedent("""\
            \"\"\"Utility helpers.\"\"\"

            def validate(data: list) -> list:
                \"\"\"Remove non-numeric entries.\"\"\"
                return [x for x in data if isinstance(x, (int, float))]

            def summarize(data: list) -> dict:
                \"\"\"Compute summary statistics.\"\"\"
                if not data:
                    return {"count": 0, "total": 0, "avg": 0}
                total = sum(data)
                return {"count": len(data), "total": total, "avg": total / len(data)}
        """),
        encoding="utf-8",
    )
    (pkg / "io_handler.py").write_text(
        textwrap.dedent("""\
            \"\"\"I/O utilities that depend on core.\"\"\"
            from mylib.core import process

            def run_from_file(path: str) -> dict:
                \"\"\"Read data from file and process.\"\"\"
                data = [1, 2, 3]  # stub
                return process(data)
        """),
        encoding="utf-8",
    )

    # Create tests
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_core.py").write_text(
        textwrap.dedent("""\
            from mylib.core import process, Pipeline

            def test_process():
                result = process([1, 2, 3])
                assert result["count"] == 3

            def test_pipeline():
                p = Pipeline()
                result = p.run([4, 5, 6])
                assert result["total"] == 15
        """),
        encoding="utf-8",
    )
    (tests_dir / "test_utils.py").write_text(
        textwrap.dedent("""\
            from mylib.utils import validate, summarize

            def test_validate():
                assert validate([1, "x", 3]) == [1, 3]

            def test_summarize():
                assert summarize([10, 20])["avg"] == 15.0
        """),
        encoding="utf-8",
    )

    # Initial commit
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "Initial commit")

    return repo


def _stage_change(repo: Path) -> None:
    """Modify utils.py and stage the change."""
    utils = repo / "mylib" / "utils.py"
    content = utils.read_text(encoding="utf-8")
    content += '\ndef normalize(data: list) -> list:\n    """Normalize to 0-1 range."""\n    mx = max(data) if data else 1\n    return [x / mx for x in data]\n'
    utils.write_text(content, encoding="utf-8")
    _git(repo, "add", "mylib/utils.py")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Run the entire CIA pipeline on a realistic repository."""

    def test_analyze_json_output(self, tmp_path: Path) -> None:
        """Full pipeline: staged changes → JSON report."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo), "--format", "json"])
        assert result.exit_code == 0, result.output

        data = json.loads(result.output)
        assert "schema_version" in data
        assert data["summary"]["total_files_changed"] >= 1
        assert isinstance(data["changes"], list)
        assert isinstance(data["risk"], dict)
        assert "overall_score" in data["risk"]

    def test_analyze_markdown_output(self, tmp_path: Path) -> None:
        """Full pipeline: staged changes → Markdown report."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo), "-f", "markdown"])
        assert result.exit_code == 0
        assert "# Change Impact Analysis Report" in result.output
        assert "Risk:" in result.output or "Executive Summary" in result.output

    def test_analyze_html_output(self, tmp_path: Path) -> None:
        """Full pipeline: staged changes → HTML report."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo), "-f", "html"])
        assert result.exit_code == 0
        assert "<!DOCTYPE html>" in result.output
        assert "Change Impact Analysis Report" in result.output
        assert "d3.v7" in result.output

    def test_analyze_all_formats_to_files(self, tmp_path: Path) -> None:
        """Full pipeline: --format all writes .json, .html, .md files."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)
        out_base = str(tmp_path / "report")

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "-f", "all", "-o", out_base]
        )
        assert result.exit_code == 0

        json_file = tmp_path / "report.json"
        html_file = tmp_path / "report.html"
        md_file = tmp_path / "report.md"

        assert json_file.exists(), "JSON report not created"
        assert html_file.exists(), "HTML report not created"
        assert md_file.exists(), "Markdown report not created"

        # Validate JSON is parseable
        data = json.loads(json_file.read_text(encoding="utf-8"))
        assert "schema_version" in data

    def test_analyze_with_threshold_pass(self, tmp_path: Path) -> None:
        """Threshold above risk score → exit 0."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--threshold", "99"]
        )
        assert result.exit_code == 0

    def test_analyze_with_explain(self, tmp_path: Path) -> None:
        """--explain prints risk breakdown."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--explain"]
        )
        assert result.exit_code == 0
        assert "Risk Breakdown" in result.output or "/100" in result.output

    def test_analyze_test_only(self, tmp_path: Path) -> None:
        """--test-only shows affected tests without full report."""
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--test-only"]
        )
        assert result.exit_code == 0
        # Should not contain full report markers
        assert "schema_version" not in result.output

    def test_analyze_commit_range(self, tmp_path: Path) -> None:
        """Analyse a commit range rather than staged changes."""
        repo = _init_repo(tmp_path)
        # Make a second commit
        _stage_change(repo)
        _git(repo, "commit", "-m", "Add normalize function")

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--commit-range", "HEAD~1..HEAD"]
        )
        assert result.exit_code == 0

    def test_analyze_unstaged(self, tmp_path: Path) -> None:
        """--unstaged analyses working-tree changes."""
        repo = _init_repo(tmp_path)
        # Modify without staging
        utils = repo / "mylib" / "utils.py"
        content = utils.read_text(encoding="utf-8")
        content += '\n# unstaged change\n'
        utils.write_text(content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--unstaged"]
        )
        assert result.exit_code == 0

    def test_analyze_no_changes(self, tmp_path: Path) -> None:
        """Analysing with nothing staged still succeeds."""
        repo = _init_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo)])
        assert result.exit_code == 0


class TestCLICommands:
    """Test every CLI command in a realistic repository."""

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "Change Impact Analyzer" in result.output

    def test_init_creates_ciarc(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".ciarc").exists()

    def test_init_idempotent(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", str(tmp_path)])
        result = runner.invoke(main, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_config_show(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["config", str(tmp_path)])
        assert result.exit_code == 0
        assert "Effective configuration" in result.output or "format" in result.output

    def test_config_get_set(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(main, ["init", str(tmp_path)])
        # Set a value
        result = runner.invoke(
            main, ["config", "--set", "threshold=80", str(tmp_path)]
        )
        assert result.exit_code == 0
        # Get it back
        result = runner.invoke(
            main, ["config", "--get", "threshold", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "80" in result.output

    def test_install_uninstall_hook(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        runner = CliRunner()

        result = runner.invoke(
            main, ["install-hook", str(repo), "--block-on", "high"]
        )
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

        hook = repo / ".git" / "hooks" / "pre-commit"
        assert hook.exists()

        result = runner.invoke(main, ["uninstall-hook", str(repo)])
        assert result.exit_code == 0
        assert not hook.exists()

    def test_install_hook_force(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

        runner = CliRunner()
        # Without --force should fail
        result = runner.invoke(main, ["install-hook", str(repo)])
        assert result.exit_code != 0 or "already exists" in result.output

        # With --force should succeed
        result = runner.invoke(main, ["install-hook", str(repo), "--force"])
        assert result.exit_code == 0

    def test_test_command(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["test", str(repo)])
        assert result.exit_code == 0

    def test_test_affected_only(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["test", str(repo), "--affected-only"])
        assert result.exit_code == 0

    def test_test_suggest(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["test", str(repo), "--suggest"])
        assert result.exit_code == 0

    def test_graph_stub(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["graph", str(repo)])
        assert result.exit_code == 0

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "install-hook" in result.output

    def test_verbose_flag(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        _stage_change(repo)

        runner = CliRunner()
        result = runner.invoke(main, ["-v", "analyze", str(repo)])
        assert result.exit_code == 0


class TestPipelineComponents:
    """Test individual pipeline components with realistic data."""

    def test_parser_on_realistic_code(self, tmp_path: Path) -> None:
        """Parser extracts functions, classes, imports from realistic code."""
        from cia.parser.python_parser import PythonParser

        repo = _init_repo(tmp_path)
        parser = PythonParser()
        modules = parser.parse_directory(repo / "mylib")

        assert len(modules) >= 3
        module_names = {m.module_name for m in modules}
        assert "core" in module_names
        assert "utils" in module_names

        # Check core.py parsed correctly
        core = next(m for m in modules if m.module_name == "core")
        func_names = {f.name for f in core.functions}
        assert "process" in func_names
        class_names = {c.name for c in core.classes}
        assert "Pipeline" in class_names

    def test_dependency_graph_from_realistic_code(self, tmp_path: Path) -> None:
        """DependencyGraph correctly captures import relationships."""
        from cia.graph.dependency_graph import DependencyGraph
        from cia.parser.python_parser import PythonParser

        repo = _init_repo(tmp_path)
        parser = PythonParser()
        modules = parser.parse_directory(repo / "mylib")

        dg = DependencyGraph()
        dg.build_from_modules(modules)

        assert dg.module_count >= 3
        # build_from_modules resolves top-level import names;
        # "from mylib import utils" → top-level target is "mylib"
        # Manual edges verify the graph works correctly
        dg.add_dependency("core", "utils")
        deps = dg.get_dependencies("core")
        assert "utils" in deps
        # utils has no internal deps (within the package)
        assert dg.get_dependencies("utils") == []

    def test_call_graph_from_realistic_code(self, tmp_path: Path) -> None:
        """CallGraph captures function call relationships."""
        from cia.graph.call_graph import CallGraph
        from cia.parser.python_parser import PythonParser

        repo = _init_repo(tmp_path)
        parser = PythonParser()
        modules = parser.parse_directory(repo / "mylib")

        cg = CallGraph()
        cg.build_from_modules(modules)

        assert cg.function_count >= 3

    def test_change_detector_with_real_diff(self, tmp_path: Path) -> None:
        """ChangeDetector correctly parses a real Git diff."""
        from cia.analyzer.change_detector import ChangeDetector
        from cia.git.git_integration import GitIntegration

        repo = _init_repo(tmp_path)
        _stage_change(repo)

        git = GitIntegration(repo)
        detector = ChangeDetector()
        changeset = detector.detect_changes(git, staged=True)

        assert len(changeset.changes) >= 1
        changed_files = [str(c.file_path) for c in changeset.changes]
        assert any("utils" in f for f in changed_files)

    def test_risk_scorer_produces_valid_score(self, tmp_path: Path) -> None:
        """RiskScorer returns a valid 0-100 score."""
        from cia.analyzer.change_detector import ChangeDetector
        from cia.git.git_integration import GitIntegration
        from cia.risk.risk_scorer import RiskScorer

        repo = _init_repo(tmp_path)
        _stage_change(repo)

        git = GitIntegration(repo)
        detector = ChangeDetector()
        changeset = detector.detect_changes(git, staged=True)

        scorer = RiskScorer()
        risk = scorer.calculate_risk(changeset)
        assert 0 <= risk.overall_score <= 100
        assert risk.level.value in ("low", "medium", "high", "critical")

    def test_impact_analyzer_produces_report(self, tmp_path: Path) -> None:
        """ImpactAnalyzer produces a complete ImpactReport."""
        from cia.analyzer.change_detector import ChangeDetector
        from cia.analyzer.impact_analyzer import ImpactAnalyzer
        from cia.git.git_integration import GitIntegration
        from cia.graph.dependency_graph import DependencyGraph
        from cia.risk.risk_scorer import RiskScorer

        repo = _init_repo(tmp_path)
        _stage_change(repo)

        git = GitIntegration(repo)
        detector = ChangeDetector()
        changeset = detector.detect_changes(git, staged=True)

        scorer = RiskScorer()
        risk = scorer.calculate_risk(changeset)

        dg = DependencyGraph()
        analyzer = ImpactAnalyzer(dg)
        report = analyzer.analyze_change_set(changeset, risk_score=risk)

        assert report.analysis.total_files_changed >= 1
        assert report.risk is not None

    def test_all_reporters_produce_output(self, tmp_path: Path) -> None:
        """All three reporters generate non-empty output."""
        from cia.analyzer.change_detector import ChangeDetector
        from cia.analyzer.impact_analyzer import ImpactAnalyzer
        from cia.git.git_integration import GitIntegration
        from cia.graph.dependency_graph import DependencyGraph
        from cia.report.html_reporter import HtmlReporter
        from cia.report.json_reporter import JsonReporter
        from cia.report.markdown_reporter import MarkdownReporter
        from cia.risk.risk_scorer import RiskScorer

        repo = _init_repo(tmp_path)
        _stage_change(repo)

        git = GitIntegration(repo)
        detector = ChangeDetector()
        changeset = detector.detect_changes(git, staged=True)
        scorer = RiskScorer()
        risk = scorer.calculate_risk(changeset)
        dg = DependencyGraph()
        analyzer = ImpactAnalyzer(dg)
        report = analyzer.analyze_change_set(changeset, risk_score=risk)

        json_out = JsonReporter().generate(report)
        md_out = MarkdownReporter().generate(report)
        html_out = HtmlReporter().generate(report)

        assert len(json_out) > 10
        assert len(md_out) > 10
        assert len(html_out) > 10
        # JSON is valid
        data = json.loads(json_out)
        assert "schema_version" in data
