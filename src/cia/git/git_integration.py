"""Git repository integration using GitPython."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError


class GitIntegration:
    """Interface for interacting with a Git repository.

    Wraps GitPython to provide a high-level API for change-impact
    analysis: querying diffs, staged/unstaged files, file contents at
    arbitrary commits, and commit-range queries.
    """

    def __init__(self, repo_path: str | Path) -> None:
        self._repo_path = Path(repo_path).resolve()
        self._repo: Repo | None = None

    # ------------------------------------------------------------------
    # Repository access
    # ------------------------------------------------------------------

    @property
    def repo(self) -> Repo:
        """Lazily open the Git repository."""
        if self._repo is None:
            try:
                self._repo = Repo(self._repo_path, search_parent_directories=True)
            except (InvalidGitRepositoryError, NoSuchPathError) as exc:
                raise ValueError(
                    f"Not a valid Git repository: {self._repo_path}"
                ) from exc
        return self._repo

    def is_git_repository(self) -> bool:
        """Return ``True`` if *repo_path* is inside a Git repository."""
        try:
            _ = self.repo
            return True
        except ValueError:
            return False

    def get_repository_root(self) -> Path:
        """Return the root directory of the Git repository."""
        return Path(self.repo.working_dir)

    # ------------------------------------------------------------------
    # Branch / commit helpers
    # ------------------------------------------------------------------

    def get_current_branch(self) -> str:
        """Return the name of the current branch."""
        if self.repo.head.is_detached:
            return f"HEAD@{self.repo.head.commit.hexsha[:8]}"
        return str(self.repo.active_branch)

    def get_head_commit_sha(self) -> str:
        """Return the SHA of the HEAD commit."""
        return str(self.repo.head.commit.hexsha)

    def is_dirty(self) -> bool:
        """Check if the working directory has uncommitted changes."""
        return self.repo.is_dirty(untracked_files=True)

    # ------------------------------------------------------------------
    # Diff helpers
    # ------------------------------------------------------------------

    def get_staged_diff(self) -> str:
        """Return the unified diff of staged changes."""
        return self.repo.git.diff("--cached")

    def get_unstaged_diff(self) -> str:
        """Return the unified diff of unstaged changes."""
        return self.repo.git.diff()

    def get_diff_between(self, ref_a: str, ref_b: str) -> str:
        """Return the unified diff between two references."""
        return self.repo.git.diff(ref_a, ref_b)

    def get_diff(self, filepath: str | Path, commit: str = "HEAD") -> str:
        """Return the diff for a specific *filepath* against *commit*.

        Returns an empty string if the file has no changes.
        """
        return self.repo.git.diff(commit, "--", str(filepath))

    # ------------------------------------------------------------------
    # File queries
    # ------------------------------------------------------------------

    def get_changed_files(self, commit_range: str | None = None) -> list[Path]:
        """Return a list of changed file paths.

        Parameters
        ----------
        commit_range:
            If given, a Git revision range such as ``"HEAD~3..HEAD"``.
            When *None* the staged changes are used.
        """
        if commit_range:
            output = self.repo.git.diff("--name-only", commit_range)
            return [Path(p) for p in output.splitlines() if p.strip()]

        diff_index = self.repo.index.diff("HEAD")
        paths: list[Path] = []
        for diff_item in diff_index:
            if diff_item.a_path:
                paths.append(Path(diff_item.a_path))
            if diff_item.b_path and diff_item.b_path != diff_item.a_path:
                paths.append(Path(diff_item.b_path))
        return paths

    def get_staged_files(self) -> list[Path]:
        """Return files that are staged (ready to commit)."""
        diff_index = self.repo.index.diff("HEAD")
        paths: list[Path] = []
        for d in diff_index:
            if d.a_path:
                paths.append(Path(d.a_path))
            if d.b_path and d.b_path != d.a_path:
                paths.append(Path(d.b_path))
        return paths

    def get_unstaged_files(self) -> list[Path]:
        """Return files that are modified but **not** staged."""
        diff_index = self.repo.index.diff(None)
        paths: list[Path] = []
        for d in diff_index:
            if d.a_path:
                paths.append(Path(d.a_path))
            if d.b_path and d.b_path != d.a_path:
                paths.append(Path(d.b_path))
        return paths

    def get_file_content(self, filepath: str | Path, commit: str = "HEAD") -> str:
        """Return the content of *filepath* at the given *commit*.

        Raises ``KeyError`` if the file does not exist at that commit.
        """
        try:
            return self.repo.git.show(f"{commit}:{filepath}")
        except Exception as exc:
            raise KeyError(
                f"File {filepath!r} not found at commit {commit!r}"
            ) from exc
