"""Comprehensive tests for GitIntegration."""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from cia.git.git_integration import GitIntegration

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repository with an initial commit."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    # Initial commit with a file
    hello = tmp_path / "hello.py"
    hello.write_text('def hello():\n    return "hello"\n', encoding="utf-8")
    repo.index.add(["hello.py"])
    repo.index.commit("Initial commit")
    return tmp_path


@pytest.fixture
def git_integration(git_repo: Path) -> GitIntegration:
    return GitIntegration(git_repo)


# ==================================================================
# Repository access
# ==================================================================


class TestRepositoryAccess:
    def test_is_git_repository(self, git_integration: GitIntegration) -> None:
        assert git_integration.is_git_repository() is True

    def test_is_not_git_repository(self, tmp_path: Path) -> None:
        gi = GitIntegration(tmp_path)
        assert gi.is_git_repository() is False

    def test_get_repository_root(self, git_integration: GitIntegration, git_repo: Path) -> None:
        root = git_integration.get_repository_root()
        assert root == git_repo

    def test_invalid_path_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "nonexistent"
        gi = GitIntegration(bad)
        with pytest.raises(ValueError, match="Not a valid Git repository"):
            _ = gi.repo


# ==================================================================
# Branch / commit helpers
# ==================================================================


class TestBranchCommit:
    def test_get_current_branch(self, git_integration: GitIntegration) -> None:
        branch = git_integration.get_current_branch()
        assert isinstance(branch, str)
        assert len(branch) > 0

    def test_get_head_commit_sha(self, git_integration: GitIntegration) -> None:
        sha = git_integration.get_head_commit_sha()
        assert len(sha) == 40

    def test_is_dirty_clean_repo(self, git_integration: GitIntegration) -> None:
        assert git_integration.is_dirty() is False

    def test_is_dirty_after_modification(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text('def hello():\n    return "modified"\n', encoding="utf-8")
        assert git_integration.is_dirty() is True


# ==================================================================
# Diff helpers
# ==================================================================


class TestDiffs:
    def test_get_staged_diff_empty(self, git_integration: GitIntegration) -> None:
        diff = git_integration.get_staged_diff()
        assert diff == ""

    def test_get_staged_diff_with_changes(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text('def hello():\n    return "updated"\n', encoding="utf-8")
        git_integration.repo.index.add(["hello.py"])
        diff = git_integration.get_staged_diff()
        assert "updated" in diff

    def test_get_unstaged_diff(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text('def hello():\n    return "unstaged"\n', encoding="utf-8")
        diff = git_integration.get_unstaged_diff()
        assert "unstaged" in diff

    def test_get_diff_between(self, git_integration: GitIntegration, git_repo: Path) -> None:
        # Make a second commit
        (git_repo / "hello.py").write_text('def hello():\n    return "v2"\n', encoding="utf-8")
        git_integration.repo.index.add(["hello.py"])
        git_integration.repo.index.commit("Second commit")
        diff = git_integration.get_diff_between("HEAD~1", "HEAD")
        assert "v2" in diff

    def test_get_diff_for_filepath(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text('def hello():\n    return "changed"\n', encoding="utf-8")
        git_integration.repo.index.add(["hello.py"])
        git_integration.repo.index.commit("Change hello")
        diff = git_integration.get_diff("hello.py", "HEAD~1")
        assert "changed" in diff


# ==================================================================
# File queries
# ==================================================================


class TestFileQueries:
    def test_get_changed_files_staged(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "new.py").write_text("x = 1\n", encoding="utf-8")
        git_integration.repo.index.add(["new.py"])
        files = git_integration.get_changed_files()
        assert any(p.name == "new.py" for p in files)

    def test_get_changed_files_commit_range(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "another.py").write_text("y = 2\n", encoding="utf-8")
        git_integration.repo.index.add(["another.py"])
        git_integration.repo.index.commit("Add another")
        files = git_integration.get_changed_files(commit_range="HEAD~1..HEAD")
        assert any(p.name == "another.py" for p in files)

    def test_get_staged_files(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "staged.py").write_text("a = 1\n", encoding="utf-8")
        git_integration.repo.index.add(["staged.py"])
        files = git_integration.get_staged_files()
        assert any(p.name == "staged.py" for p in files)

    def test_get_unstaged_files(self, git_integration: GitIntegration, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text('def hello():\n    return "unstaged edit"\n', encoding="utf-8")
        files = git_integration.get_unstaged_files()
        assert any(p.name == "hello.py" for p in files)

    def test_get_file_content(self, git_integration: GitIntegration) -> None:
        content = git_integration.get_file_content("hello.py", "HEAD")
        assert "def hello" in content

    def test_get_file_content_missing_raises(self, git_integration: GitIntegration) -> None:
        with pytest.raises(KeyError):
            git_integration.get_file_content("nonexistent.py", "HEAD")

    def test_get_changed_files_no_range_no_staged(self, git_integration: GitIntegration) -> None:
        files = git_integration.get_changed_files()
        assert files == []
