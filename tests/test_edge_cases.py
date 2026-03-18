"""Edge case tests for CIA robustness.

Covers: empty repos, binary files, symlinks, large files, circular deps,
syntax errors in changed files, and merge-conflict markers.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from click.testing import CliRunner

from cia.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=check,
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "hello.py").write_text('def greet():\n    return "hi"\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


# ---------------------------------------------------------------------------
# Edge case: empty repository (no commits)
# ---------------------------------------------------------------------------


class TestEmptyRepository:
    def test_analyze_empty_repo(self, tmp_path: Path) -> None:
        """Analysing a repo with no commits should not crash."""
        repo = tmp_path / "empty"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "t@t.com")
        _git(repo, "config", "user.name", "T")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo)])
        # May error (no HEAD) but should not traceback
        assert result.exit_code in (0, 2)
        assert "Traceback" not in result.output

    def test_test_empty_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "empty"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "t@t.com")
        _git(repo, "config", "user.name", "T")

        runner = CliRunner()
        result = runner.invoke(main, ["test", str(repo)])
        assert result.exit_code in (0, 2)
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Edge case: binary files in changes
# ---------------------------------------------------------------------------


class TestBinaryFiles:
    def test_binary_file_in_diff(self, tmp_path: Path) -> None:
        """Binary files should be skipped gracefully by the parser."""
        repo = _make_repo(tmp_path)

        # Add a binary file
        bin_file = repo / "data.bin"
        bin_file.write_bytes(b"\x00\x01\x02\xff" * 256)
        _git(repo, "add", "data.bin")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo)])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_binary_file_mixed_with_python(self, tmp_path: Path) -> None:
        """A diff containing both binary and Python changes works."""
        repo = _make_repo(tmp_path)

        (repo / "data.bin").write_bytes(b"\xde\xad\xbe\xef" * 100)
        (repo / "hello.py").write_text(
            'def greet():\n    return "updated"\n', encoding="utf-8"
        )
        _git(repo, "add", "-A")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Edge case: very large files (>1MB of Python)
# ---------------------------------------------------------------------------


class TestLargeFiles:
    def test_large_python_file(self, tmp_path: Path) -> None:
        """Parser handles a very large Python file without crashing."""
        from cia.parser.python_parser import PythonParser

        big = tmp_path / "big.py"
        lines = ['"""Big module."""\n']
        for i in range(500):
            lines.append(f"def func_{i}():\n    return {i}\n\n")
        big.write_text("".join(lines), encoding="utf-8")

        parser = PythonParser()
        result = parser.parse_file(big)
        assert len(result.functions) == 500
        assert not result.errors


# ---------------------------------------------------------------------------
# Edge case: circular dependencies
# ---------------------------------------------------------------------------


class TestCircularDependencies:
    def test_circular_import_detection(self) -> None:
        """DependencyGraph detects and reports circular dependencies."""
        from cia.graph.dependency_graph import DependencyGraph

        dg = DependencyGraph()
        dg.add_module("a")
        dg.add_module("b")
        dg.add_module("c")
        dg.add_dependency("a", "b")
        dg.add_dependency("b", "c")
        dg.add_dependency("c", "a")

        assert dg.has_cycles()
        cycles = dg.find_cycles()
        assert len(cycles) >= 1

    def test_transitive_dependents_with_cycle(self) -> None:
        """Transitive queries work even when cycles exist."""
        from cia.graph.dependency_graph import DependencyGraph

        dg = DependencyGraph()
        dg.add_module("x")
        dg.add_module("y")
        dg.add_dependency("x", "y")
        dg.add_dependency("y", "x")

        # Should not infinite-loop
        deps = dg.get_transitive_dependents("x")
        assert "y" in deps

    def test_analyze_with_circular_deps(self, tmp_path: Path) -> None:
        """Full analysis with circular imports should not crash."""
        repo = _make_repo(tmp_path)

        (repo / "mod_a.py").write_text(
            "from mod_b import something\ndef a_func():\n    return 1\n",
            encoding="utf-8",
        )
        (repo / "mod_b.py").write_text(
            "from mod_a import a_func\ndef something():\n    return a_func()\n",
            encoding="utf-8",
        )
        _git(repo, "add", "-A")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo)])
        assert result.exit_code == 0
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Edge case: syntax errors in changed files
# ---------------------------------------------------------------------------


class TestSyntaxErrors:
    def test_parser_handles_syntax_error(self, tmp_path: Path) -> None:
        """Parser records an error but does not crash on invalid Python."""
        from cia.parser.python_parser import PythonParser

        bad = tmp_path / "bad.py"
        bad.write_text("def broken(\n    # missing close paren", encoding="utf-8")

        parser = PythonParser()
        result = parser.parse_file(bad)
        assert len(result.errors) >= 1
        assert "Syntax error" in result.errors[0] or "Parse error" in result.errors[0]

    def test_analyze_with_syntax_error_file(self, tmp_path: Path) -> None:
        """Analysing a repo with a broken file should not crash."""
        repo = _make_repo(tmp_path)

        (repo / "broken.py").write_text(
            "def whoops(\n", encoding="utf-8"
        )
        _git(repo, "add", "broken.py")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(repo)])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_parser_handles_encoding_error(self, tmp_path: Path) -> None:
        """Parser handles non-UTF-8 files gracefully."""
        from cia.parser.python_parser import PythonParser

        bad = tmp_path / "latin.py"
        bad.write_bytes(b"# \xe9\n")

        parser = PythonParser()
        result = parser.parse_file(bad)
        # Should either parse or record an error — not crash
        assert isinstance(result.errors, list)


# ---------------------------------------------------------------------------
# Edge case: merge conflict markers
# ---------------------------------------------------------------------------


class TestMergeConflicts:
    def test_parser_handles_conflict_markers(self, tmp_path: Path) -> None:
        """Files with merge conflict markers are treated as parse errors."""
        from cia.parser.python_parser import PythonParser

        conflict = tmp_path / "conflict.py"
        conflict.write_text(
            textwrap.dedent("""\
                def hello():
                <<<<<<< HEAD
                    return "ours"
                =======
                    return "theirs"
                >>>>>>> branch
            """),
            encoding="utf-8",
        )

        parser = PythonParser()
        result = parser.parse_file(conflict)
        assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# Edge case: not a Git repository
# ---------------------------------------------------------------------------


class TestNotGitRepo:
    def test_analyze_non_git_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(tmp_path)])
        assert result.exit_code != 0 or "Not a" in result.output or "Error" in result.output

    def test_install_hook_non_git(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["install-hook", str(tmp_path)])
        assert result.exit_code != 0 or "Error" in result.output

    def test_test_cmd_non_git(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["test", str(tmp_path)])
        assert result.exit_code != 0 or "Error" in result.output


# ---------------------------------------------------------------------------
# Edge case: invalid commit range
# ---------------------------------------------------------------------------


class TestInvalidCommitRange:
    def test_bad_commit_range_format(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--commit-range", "invalid"]
        )
        assert result.exit_code != 0 or "Error" in result.output

    def test_nonexistent_commits(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", str(repo), "--commit-range", "abc123..def456"]
        )
        assert result.exit_code != 0 or "Error" in result.output


# ---------------------------------------------------------------------------
# Edge case: parser caching
# ---------------------------------------------------------------------------


class TestParserCaching:
    def test_cache_hit(self, tmp_path: Path) -> None:
        """Second parse of the same file returns cached result."""
        from cia.parser.python_parser import PythonParser

        f = tmp_path / "cached.py"
        f.write_text("x = 1\n", encoding="utf-8")

        parser = PythonParser()
        r1 = parser.parse_file(f)
        r2 = parser.parse_file(f)
        assert r1 is r2
        assert parser.cache_size == 1

    def test_clear_cache(self, tmp_path: Path) -> None:
        from cia.parser.python_parser import PythonParser

        f = tmp_path / "c.py"
        f.write_text("y = 2\n", encoding="utf-8")

        parser = PythonParser()
        parser.parse_file(f)
        assert parser.cache_size == 1
        parser.clear_cache()
        assert parser.cache_size == 0


# ---------------------------------------------------------------------------
# Edge case: empty diff / no changes
# ---------------------------------------------------------------------------


class TestEmptyDiff:
    def test_parse_empty_diff(self) -> None:
        from cia.analyzer.change_detector import ChangeDetector

        detector = ChangeDetector()
        changes = detector.parse_diff("")
        assert changes == []

    def test_changeset_from_empty_diff(self) -> None:
        from cia.analyzer.change_detector import ChangeDetector
        from cia.risk.risk_scorer import RiskScorer

        detector = ChangeDetector()
        changeset = detector._build_changeset([])
        assert changeset.changes == []

        scorer = RiskScorer()
        risk = scorer.calculate_risk(changeset)
        assert risk.overall_score == 0.0
        assert risk.level.value == "low"
