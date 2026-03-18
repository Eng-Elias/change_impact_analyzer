"""Tests for CI/CD configuration files.

Validates that all workflow YAML files are well-formed and contain
the expected structure (triggers, jobs, steps, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Root of the repository
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _load_workflow(name: str) -> dict:
    """Load a workflow YAML file and return the parsed dict."""
    path = WORKFLOWS_DIR / name
    assert path.exists(), f"Workflow file not found: {path}"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"{name} did not parse as a YAML mapping"
    return data


def _get_triggers(wf: dict) -> dict:
    """Get workflow triggers — PyYAML parses the YAML key ``on`` as ``True``."""
    return wf.get("on") or wf.get(True, {})


# ==================================================================
# Generic validity
# ==================================================================


class TestWorkflowValidity:
    """Every YAML file in .github/workflows/ must be valid."""

    @pytest.fixture(params=["ci.yml", "release.yml", "cia.yml"])
    def workflow(self, request: pytest.FixtureRequest) -> dict:
        return _load_workflow(request.param)

    def test_is_valid_yaml(self, workflow: dict) -> None:
        assert "name" in workflow
        # PyYAML parses 'on' as True
        assert "on" in workflow or True in workflow
        assert "jobs" in workflow

    def test_has_at_least_one_job(self, workflow: dict) -> None:
        assert len(workflow["jobs"]) >= 1

    def test_every_job_has_steps_or_uses(self, workflow: dict) -> None:
        for job_name, job in workflow["jobs"].items():
            assert "steps" in job, f"Job '{job_name}' is missing 'steps'"
            assert len(job["steps"]) >= 1


# ==================================================================
# ci.yml
# ==================================================================


class TestCIWorkflow:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.wf = _load_workflow("ci.yml")

    def test_name(self) -> None:
        assert self.wf["name"] == "CI"

    def test_triggers(self) -> None:
        triggers = _get_triggers(self.wf)
        assert "push" in triggers
        assert "pull_request" in triggers

    def test_has_lint_job(self) -> None:
        assert "lint" in self.wf["jobs"]

    def test_has_typecheck_job(self) -> None:
        assert "typecheck" in self.wf["jobs"]

    def test_has_test_job(self) -> None:
        assert "test" in self.wf["jobs"]

    def test_has_dogfood_job(self) -> None:
        assert "dogfood" in self.wf["jobs"]

    def test_matrix_os(self) -> None:
        matrix = self.wf["jobs"]["test"]["strategy"]["matrix"]
        os_list = matrix["os"]
        assert "ubuntu-latest" in os_list
        assert "macos-latest" in os_list
        assert "windows-latest" in os_list

    def test_matrix_python_versions(self) -> None:
        matrix = self.wf["jobs"]["test"]["strategy"]["matrix"]
        versions = matrix["python-version"]
        assert "3.11" in versions
        assert "3.12" in versions

    def test_lint_runs_ruff(self) -> None:
        steps = self.wf["jobs"]["lint"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("ruff check" in r for r in run_cmds)

    def test_typecheck_runs_mypy(self) -> None:
        steps = self.wf["jobs"]["typecheck"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("mypy" in r for r in run_cmds)

    def test_test_runs_pytest_with_coverage(self) -> None:
        steps = self.wf["jobs"]["test"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("pytest" in r and "--cov" in r for r in run_cmds)

    def test_codecov_upload(self) -> None:
        steps = self.wf["jobs"]["test"]["steps"]
        uses = [s.get("uses", "") for s in steps]
        assert any("codecov" in u for u in uses)

    def test_dogfood_runs_cia(self) -> None:
        steps = self.wf["jobs"]["dogfood"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("cia analyze" in r for r in run_cmds)

    def test_install_step(self) -> None:
        steps = self.wf["jobs"]["test"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any('pip install -e ".[dev]"' in r for r in run_cmds)

    def test_coverage_threshold(self) -> None:
        steps = self.wf["jobs"]["test"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("--cov-fail-under=70" in r for r in run_cmds)


# ==================================================================
# release.yml
# ==================================================================


class TestReleaseWorkflow:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.wf = _load_workflow("release.yml")

    def test_name(self) -> None:
        assert self.wf["name"] == "Release"

    def test_trigger_on_tag(self) -> None:
        triggers = _get_triggers(self.wf)
        assert "push" in triggers
        tags = triggers["push"].get("tags", [])
        assert any("v*" in t for t in tags)

    def test_has_test_job(self) -> None:
        assert "test" in self.wf["jobs"]

    def test_has_publish_job(self) -> None:
        assert "publish" in self.wf["jobs"]

    def test_has_release_job(self) -> None:
        assert "release" in self.wf["jobs"]

    def test_publish_needs_test(self) -> None:
        needs = self.wf["jobs"]["publish"].get("needs", [])
        assert "test" in needs

    def test_release_needs_publish(self) -> None:
        needs = self.wf["jobs"]["release"].get("needs", [])
        assert "publish" in needs

    def test_build_step(self) -> None:
        steps = self.wf["jobs"]["publish"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("python -m build" in r for r in run_cmds)

    def test_pypi_publish_action(self) -> None:
        steps = self.wf["jobs"]["publish"]["steps"]
        uses = [s.get("uses", "") for s in steps]
        assert any("pypi-publish" in u for u in uses)

    def test_github_release_action(self) -> None:
        steps = self.wf["jobs"]["release"]["steps"]
        uses = [s.get("uses", "") for s in steps]
        assert any("gh-release" in u for u in uses)

    def test_permissions(self) -> None:
        perms = self.wf.get("permissions", {})
        assert "contents" in perms
        assert "id-token" in perms


# ==================================================================
# cia.yml
# ==================================================================


class TestCIAWorkflow:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.wf = _load_workflow("cia.yml")

    def test_name(self) -> None:
        assert "CIA" in self.wf["name"] or "cia" in self.wf["name"].lower()

    def test_trigger_on_pull_request(self) -> None:
        triggers = _get_triggers(self.wf)
        assert "pull_request" in triggers

    def test_has_analyze_job(self) -> None:
        assert "analyze" in self.wf["jobs"]

    def test_runs_cia_analyze(self) -> None:
        steps = self.wf["jobs"]["analyze"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("cia analyze" in r for r in run_cmds)

    def test_posts_pr_comment(self) -> None:
        steps = self.wf["jobs"]["analyze"]["steps"]
        uses = [s.get("uses", "") for s in steps]
        assert any("sticky-pull-request-comment" in u for u in uses)

    def test_threshold_check_step(self) -> None:
        steps = self.wf["jobs"]["analyze"]["steps"]
        step_names = [s.get("name", "").lower() for s in steps]
        assert any("threshold" in n or "risk" in n for n in step_names)

    def test_permissions_include_pr_write(self) -> None:
        perms = self.wf.get("permissions", {})
        assert perms.get("pull-requests") == "write"


# ==================================================================
# .pre-commit-config.yaml
# ==================================================================


class TestPreCommitConfig:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        path = REPO_ROOT / ".pre-commit-config.yaml"
        assert path.exists()
        with open(path, encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

    def test_is_valid_yaml(self) -> None:
        assert isinstance(self.cfg, dict)
        assert "repos" in self.cfg

    def test_has_black_hook(self) -> None:
        repos = self.cfg["repos"]
        hooks = [h["id"] for r in repos for h in r.get("hooks", [])]
        assert "black" in hooks

    def test_has_ruff_hook(self) -> None:
        repos = self.cfg["repos"]
        hooks = [h["id"] for r in repos for h in r.get("hooks", [])]
        assert "ruff" in hooks

    def test_has_mypy_hook(self) -> None:
        repos = self.cfg["repos"]
        hooks = [h["id"] for r in repos for h in r.get("hooks", [])]
        assert "mypy" in hooks

    def test_has_pytest_hook(self) -> None:
        repos = self.cfg["repos"]
        hooks = [h["id"] for r in repos for h in r.get("hooks", [])]
        assert "pytest-quick" in hooks

    def test_has_cia_hook(self) -> None:
        repos = self.cfg["repos"]
        hooks = [h["id"] for r in repos for h in r.get("hooks", [])]
        assert "cia-self-analysis" in hooks

    def test_standard_hooks(self) -> None:
        repos = self.cfg["repos"]
        hooks = [h["id"] for r in repos for h in r.get("hooks", [])]
        assert "trailing-whitespace" in hooks
        assert "end-of-file-fixer" in hooks
        assert "check-yaml" in hooks


# ==================================================================
# tox.ini
# ==================================================================


class TestToxConfig:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.path = REPO_ROOT / "tox.ini"
        assert self.path.exists()
        self.content = self.path.read_text(encoding="utf-8")

    def test_envlist_has_python_versions(self) -> None:
        assert "py311" in self.content
        assert "py312" in self.content

    def test_envlist_has_lint(self) -> None:
        assert "lint" in self.content

    def test_envlist_has_typecheck(self) -> None:
        assert "typecheck" in self.content

    def test_has_docs_env(self) -> None:
        assert "[testenv:docs]" in self.content

    def test_has_format_env(self) -> None:
        assert "[testenv:format]" in self.content

    def test_coverage_threshold(self) -> None:
        assert "--cov-fail-under=70" in self.content

    def test_docs_uses_sphinx(self) -> None:
        assert "sphinx-build" in self.content
