"""Comprehensive tests for CLI commands (Prompt 8).

Tests cover:
- All commands: analyze, version, init, config, install-hook, uninstall-hook, graph, test
- Argument parsing and option handling
- Configuration loading integration
- Error handling and exit codes
- Format options and output routing
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from git import Repo

from cia.cli import (
    EXIT_ERROR,
    EXIT_HIGH_RISK,
    EXIT_OK,
    main,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repo with an initial commit."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    hello = tmp_path / "hello.py"
    hello.write_text("x = 1\n", encoding="utf-8")
    repo.index.add(["hello.py"])
    repo.index.commit("Initial commit")
    return tmp_path


# ==================================================================
# Exit code constants
# ==================================================================


class TestExitCodes:
    def test_exit_ok(self) -> None:
        assert EXIT_OK == 0

    def test_exit_high_risk(self) -> None:
        assert EXIT_HIGH_RISK == 1

    def test_exit_error(self) -> None:
        assert EXIT_ERROR == 2


# ==================================================================
# cia --version
# ==================================================================


class TestVersionFlag:
    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "cia" in result.output

    def test_verbose_flag(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["-v", "analyze", str(git_repo)])
        assert result.exit_code == 0
        assert "Analyzing changes in" in result.output


# ==================================================================
# cia version
# ==================================================================


class TestVersionCommand:
    def test_shows_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "Change Impact Analyzer" in result.output

    def test_shows_python_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["version"])
        assert "Python" in result.output

    def test_shows_platform(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["version"])
        assert "Platform" in result.output

    def test_shows_click_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["version"])
        assert "Click" in result.output


# ==================================================================
# cia init
# ==================================================================


class TestInitCommand:
    def test_creates_ciarc(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["init", str(tmp_path)])
        assert result.exit_code == 0
        rc = tmp_path / ".ciarc"
        assert rc.exists()
        assert "Created configuration file" in result.output

    def test_does_not_overwrite(self, runner: CliRunner, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("existing\n", encoding="utf-8")
        result = runner.invoke(main, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exists" in result.output
        assert rc.read_text(encoding="utf-8") == "existing\n"

    def test_ciarc_content_is_valid_toml(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(main, ["init", str(tmp_path)])
        rc = tmp_path / ".ciarc"
        import tomllib
        with open(rc, "rb") as f:
            data = tomllib.load(f)
        assert "analysis" in data


# ==================================================================
# cia config
# ==================================================================


class TestConfigCommand:
    def test_show_defaults(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", str(tmp_path)])
        assert result.exit_code == 0
        assert "Effective configuration" in result.output
        assert "format" in result.output

    def test_show_with_file(self, runner: CliRunner, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text('[analysis]\nformat = "html"\n', encoding="utf-8")
        result = runner.invoke(main, ["config", str(tmp_path)])
        assert result.exit_code == 0
        assert "Config file" in result.output
        assert "html" in result.output

    def test_get_existing_key(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", "--get", "format", str(tmp_path)])
        assert result.exit_code == 0
        assert "format = json" in result.output

    def test_get_missing_key(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", "--get", "nonexistent", str(tmp_path)])
        assert "Key not found" in result.output

    def test_set_value(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            main, ["config", "--set", "analysis.format=html", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Set" in result.output
        rc = tmp_path / ".ciarc"
        assert rc.exists()

    def test_set_creates_ciarc_if_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(main, ["config", "--set", "format=markdown", str(tmp_path)])
        rc = tmp_path / ".ciarc"
        assert rc.exists()

    def test_set_invalid_format(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", "--set", "no_equals_sign", str(tmp_path)])
        assert "key=value" in result.output

    def test_edit_no_ciarc(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", "--edit", str(tmp_path)])
        assert "No .ciarc found" in result.output

    def test_edit_opens_editor(self, runner: CliRunner, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("x = 1\n", encoding="utf-8")
        with patch("cia.cli.subprocess.run") as mock_run:
            mock_run.return_value = None
            runner.invoke(main, ["config", "--edit", str(tmp_path)])
            assert mock_run.called

    def test_edit_with_editor_env(self, runner: CliRunner, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("x = 1\n", encoding="utf-8")
        with patch("cia.cli.subprocess.run") as mock_run, \
             patch.dict(os.environ, {"EDITOR": "myeditor"}, clear=False):
            mock_run.return_value = None
            runner.invoke(main, ["config", "--edit", str(tmp_path)])
            args = mock_run.call_args[0][0]
            assert args[0] == "myeditor"

    def test_edit_editor_error(self, runner: CliRunner, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("x = 1\n", encoding="utf-8")
        with patch("cia.cli.subprocess.run", side_effect=FileNotFoundError("no editor")):
            result = runner.invoke(main, ["config", "--edit", str(tmp_path)])
            assert "Error launching editor" in result.output

    def test_no_config_file_message(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", str(tmp_path)])
        assert "No .ciarc file found" in result.output


# ==================================================================
# cia analyze
# ==================================================================


class TestAnalyzeCommand:
    def test_default_json(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["analyze", str(git_repo)])
        assert result.exit_code == 0
        assert "schema_version" in result.output

    def test_verbose(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["-v", "analyze", str(git_repo)])
        assert result.exit_code == 0
        assert "Analyzing changes in" in result.output
        assert "Output format" in result.output

    def test_format_html(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["analyze", str(git_repo), "-f", "html"])
        assert result.exit_code == 0
        assert "<!DOCTYPE html>" in result.output

    def test_format_markdown(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["analyze", str(git_repo), "-f", "markdown"])
        assert result.exit_code == 0
        assert "# Change Impact Analysis Report" in result.output

    def test_format_all_to_files(self, runner: CliRunner, git_repo: Path) -> None:
        base = git_repo / "report"
        result = runner.invoke(
            main, ["analyze", str(git_repo), "-f", "all", "-o", str(base)]
        )
        assert result.exit_code == 0
        assert (git_repo / "report.json").exists()
        assert (git_repo / "report.html").exists()
        assert (git_repo / "report.md").exists()

    def test_output_file_json(self, runner: CliRunner, git_repo: Path) -> None:
        out = git_repo / "r.json"
        result = runner.invoke(
            main, ["analyze", str(git_repo), "-o", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        assert "schema_version" in out.read_text(encoding="utf-8")

    def test_output_file_html(self, runner: CliRunner, git_repo: Path) -> None:
        out = git_repo / "r.html"
        result = runner.invoke(
            main, ["analyze", str(git_repo), "-f", "html", "-o", str(out)]
        )
        assert result.exit_code == 0
        assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")

    def test_output_file_markdown(self, runner: CliRunner, git_repo: Path) -> None:
        out = git_repo / "r.md"
        result = runner.invoke(
            main, ["analyze", str(git_repo), "-f", "markdown", "-o", str(out)]
        )
        assert result.exit_code == 0
        assert "# Change Impact" in out.read_text(encoding="utf-8")

    def test_unstaged(self, runner: CliRunner, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        result = runner.invoke(main, ["analyze", str(git_repo), "--unstaged"])
        assert result.exit_code == 0
        assert "schema_version" in result.output

    def test_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        repo = Repo(git_repo)
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        repo.index.add(["hello.py"])
        repo.index.commit("Second commit")
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--commit-range", "HEAD~1..HEAD"]
        )
        assert result.exit_code == 0
        assert "schema_version" in result.output

    def test_invalid_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--commit-range", "BADRANGE"]
        )
        assert result.exit_code != 0 or "Error" in result.output

    def test_explain(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["analyze", str(git_repo), "--explain"])
        assert result.exit_code == 0
        assert "Risk Breakdown" in result.output

    def test_threshold_pass(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--threshold", "100"]
        )
        assert result.exit_code == 0

    def test_test_only_flag(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--test-only"]
        )
        assert result.exit_code == 0
        # Should show test info, not a full JSON report
        assert "schema_version" not in result.output


class TestAnalyzeErrorHandling:
    def test_not_a_git_repo(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["analyze", str(tmp_path)])
        assert "Error" in result.output

    def test_verbose_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        repo = Repo(git_repo)
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        repo.index.add(["hello.py"])
        repo.index.commit("Second")
        result = runner.invoke(
            main, ["-v", "analyze", str(git_repo), "--commit-range", "HEAD~1..HEAD"]
        )
        assert result.exit_code == 0
        assert "Commit range" in result.output

    def test_threshold_fail(self, runner: CliRunner, git_repo: Path) -> None:
        # Stage a real change so risk score > 0
        (git_repo / "hello.py").write_text("x = 2\ny = 3\n" * 10, encoding="utf-8")
        repo = Repo(git_repo)
        repo.index.add(["hello.py"])
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--threshold", "0"]
        )
        # Risk score should exceed 0
        assert "FAIL" in result.output or result.exit_code != 0

    def test_explain_with_suggestions(self, runner: CliRunner, git_repo: Path) -> None:
        # Make a change so there are risk suggestions
        (git_repo / "hello.py").write_text("x = 2\ny = 3\n" * 50, encoding="utf-8")
        repo = Repo(git_repo)
        repo.index.add(["hello.py"])
        result = runner.invoke(
            main, ["analyze", str(git_repo), "--explain"]
        )
        assert result.exit_code == 0
        assert "Risk Breakdown" in result.output


# ==================================================================
# cia install-hook / uninstall-hook
# ==================================================================


class TestInstallHookCommand:
    def test_install_default(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(main, ["install-hook", str(git_repo)])
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    def test_install_with_block_on(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(
            main, ["install-hook", str(git_repo), "--block-on", "high"]
        )
        assert result.exit_code == 0
        assert "high" in result.output.lower()

    def test_install_no_git(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["install-hook", str(tmp_path)])
        assert "Error" in result.output or result.exit_code != 0

    def test_force_overwrites_existing(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/sh\necho other\n", encoding="utf-8")
        result = runner.invoke(
            main, ["install-hook", str(git_repo), "--force"]
        )
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    def test_no_force_blocks_existing(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/sh\necho other\n", encoding="utf-8")
        result = runner.invoke(main, ["install-hook", str(git_repo)])
        assert "already exists" in result.output or "force" in result.output.lower()

    def test_local_flag(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(main, ["install-hook", str(git_repo), "--local"])
        assert result.exit_code == 0
        assert "locally" in result.output

    def test_global_flag(self, runner: CliRunner, git_repo: Path) -> None:
        with patch("cia.cli.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "", "stderr": "", "returncode": 0,
            })()
            result = runner.invoke(main, ["install-hook", str(git_repo), "--global"])
            assert result.exit_code == 0
            assert "globally" in result.output

    def test_global_flag_error(self, runner: CliRunner, git_repo: Path) -> None:
        with patch("cia.cli.subprocess.run", side_effect=OSError("git not found")):
            result = runner.invoke(
                main, ["install-hook", str(git_repo), "--global"]
            )
            assert "Error" in result.output


class TestUninstallHookCommand:
    def test_uninstall_not_installed(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["uninstall-hook", str(git_repo)])
        assert result.exit_code == 0
        assert "no cia hook" in result.output.lower()

    def test_uninstall_after_install(self, runner: CliRunner, git_repo: Path) -> None:
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        runner.invoke(main, ["install-hook", str(git_repo)])
        result = runner.invoke(main, ["uninstall-hook", str(git_repo)])
        assert result.exit_code == 0
        assert "removed" in result.output.lower()


# ==================================================================
# cia graph
# ==================================================================


class TestGraphCommand:
    def test_graph_stub(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["graph", str(git_repo)])
        assert result.exit_code == 0

    def test_graph_verbose(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["-v", "graph", str(git_repo)])
        assert result.exit_code == 0
        assert "Building dependency graph" in result.output


# ==================================================================
# cia test
# ==================================================================


class TestTestCommand:
    def test_default(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(main, ["test", str(git_repo)])
        assert result.exit_code == 0

    def test_not_a_repo(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["test", str(tmp_path)])
        assert "Error" in result.output

    def test_affected_only_no_affected(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["test", str(git_repo), "--affected-only"]
        )
        assert result.exit_code == 0
        # No staged changes → no affected tests
        assert "No tests affected" in result.output

    def test_affected_only_with_tests(self, runner: CliRunner, git_repo: Path) -> None:
        # Create a test file that maps to hello.py
        tests_dir = git_repo / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_hello.py").write_text(
            "import hello\ndef test_x(): assert hello.x == 1\n",
            encoding="utf-8",
        )
        repo = Repo(git_repo)
        repo.index.add(["tests/test_hello.py"])
        repo.index.commit("Add test")
        # Now modify hello.py and stage it
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        repo.index.add(["hello.py"])
        result = runner.invoke(
            main, ["test", str(git_repo), "--affected-only"]
        )
        assert result.exit_code == 0

    def test_suggest(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["test", str(git_repo), "--suggest"]
        )
        assert result.exit_code == 0

    def test_suggest_with_staged_change(self, runner: CliRunner, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text("x = 2\ny = 3\n", encoding="utf-8")
        repo = Repo(git_repo)
        repo.index.add(["hello.py"])
        result = runner.invoke(
            main, ["test", str(git_repo), "--suggest"]
        )
        assert result.exit_code == 0

    def test_unstaged(self, runner: CliRunner, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        result = runner.invoke(
            main, ["test", str(git_repo), "--unstaged"]
        )
        assert result.exit_code == 0

    def test_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        repo = Repo(git_repo)
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        repo.index.add(["hello.py"])
        repo.index.commit("Second")
        result = runner.invoke(
            main, ["test", str(git_repo), "--commit-range", "HEAD~1..HEAD"]
        )
        assert result.exit_code == 0

    def test_invalid_commit_range(self, runner: CliRunner, git_repo: Path) -> None:
        result = runner.invoke(
            main, ["test", str(git_repo), "--commit-range", "BADRANGE"]
        )
        assert "Error" in result.output

    def test_verbose_affected_only(self, runner: CliRunner, git_repo: Path) -> None:
        tests_dir = git_repo / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_hello.py").write_text(
            "import hello\ndef test_x(): pass\n", encoding="utf-8"
        )
        repo = Repo(git_repo)
        repo.index.add(["tests/test_hello.py"])
        repo.index.commit("Add test")
        (git_repo / "hello.py").write_text("x = 2\n", encoding="utf-8")
        repo.index.add(["hello.py"])
        result = runner.invoke(
            main, ["-v", "test", str(git_repo), "--affected-only"]
        )
        assert result.exit_code == 0


# ==================================================================
# Help text
# ==================================================================


class TestHelpText:
    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Change Impact Analyzer" in result.output

    def test_analyze_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--threshold" in result.output
        assert "--test-only" in result.output

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0
        assert "--set" in result.output
        assert "--get" in result.output
        assert "--edit" in result.output

    def test_init_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert ".ciarc" in result.output

    def test_install_hook_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["install-hook", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output
        assert "--block-on" in result.output

    def test_version_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["version", "--help"])
        assert result.exit_code == 0
