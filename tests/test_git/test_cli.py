"""Comprehensive tests for CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from git import Repo

from cia.cli import main


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repo with an initial commit."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    hello = tmp_path / "hello.py"
    hello.write_text('x = 1\n', encoding="utf-8")
    repo.index.add(["hello.py"])
    repo.index.commit("Initial commit")
    return tmp_path


# ==================================================================
# cia --version
# ==================================================================


class TestVersion:
    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "cia" in result.output


# ==================================================================
# cia analyze
# ==================================================================


class TestAnalyze:
    def test_analyze_default(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["analyze", str(git_repo)])
        assert result.exit_code == 0
        assert "total_changes" in result.output

    def test_analyze_verbose(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["-v", "analyze", str(git_repo)])
        assert result.exit_code == 0
        assert "Analyzing changes in" in result.output

    def test_analyze_unstaged(self, runner: CliRunner, git_repo: Path) -> None:
        # Modify a file without staging
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        result = runner.invoke(main, ["analyze", str(git_repo), "--unstaged"])
        assert result.exit_code == 0
        assert "total_changes" in result.output

    def test_analyze_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        # Make a second commit
        repo = Repo(git_repo)
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        repo.index.add(["hello.py"])
        repo.index.commit("Second commit")
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--commit-range", "HEAD~1..HEAD"]
        )
        assert result.exit_code == 0
        assert "total_changes" in result.output

    def test_analyze_invalid_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--commit-range", "BADRANGE"]
        )
        assert result.exit_code != 0 or "Error" in result.output

    def test_analyze_output_file(self, runner: CliRunner, git_repo: Path) -> None:
        out_file = git_repo / "report.json"
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--output", str(out_file)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "total_changes" in content

    def test_analyze_not_a_repo(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["analyze", str(tmp_path)])
        assert "Error" in result.output


# ==================================================================
# cia install-hook / uninstall-hook
# ==================================================================


class TestHookCommands:
    def test_install_hook(self, runner: CliRunner, git_repo: Path) -> None:
        # Ensure .git/hooks exists
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(main, ["install-hook", str(git_repo)])
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    def test_install_hook_with_block_on(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(
            main, ["install-hook", str(git_repo), "--block-on", "high"]
        )
        assert result.exit_code == 0
        assert "high" in result.output.lower()

    def test_install_hook_no_git(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["install-hook", str(tmp_path)])
        assert "Error" in result.output or result.exit_code != 0

    def test_uninstall_hook_not_installed(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["uninstall-hook", str(git_repo)])
        assert result.exit_code == 0
        assert "no cia hook" in result.output.lower()

    def test_uninstall_hook_after_install(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        runner.invoke(main, ["install-hook", str(git_repo)])
        result = runner.invoke(main, ["uninstall-hook", str(git_repo)])
        assert result.exit_code == 0
        assert "removed" in result.output.lower()


# ==================================================================
# cia graph (stub)
# ==================================================================


class TestGraphCommand:
    def test_graph_stub(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["graph", str(git_repo)])
        assert result.exit_code == 0
