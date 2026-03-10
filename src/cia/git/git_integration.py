"""Git repository integration using GitPython."""

from __future__ import annotations

from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError


class GitIntegration:
    """Interface for interacting with a Git repository."""

    def __init__(self, repo_path: str | Path) -> None:
        self._repo_path = Path(repo_path)
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Lazily open the Git repository."""
        if self._repo is None:
            try:
                self._repo = Repo(self._repo_path)
            except (InvalidGitRepositoryError, NoSuchPathError) as exc:
                raise ValueError(
                    f"Not a valid Git repository: {self._repo_path}"
                ) from exc
        return self._repo

    def get_staged_diff(self) -> str:
        """Return the unified diff of staged changes."""
        return self.repo.git.diff("--cached")

    def get_unstaged_diff(self) -> str:
        """Return the unified diff of unstaged changes."""
        return self.repo.git.diff()

    def get_diff_between(self, ref_a: str, ref_b: str) -> str:
        """Return the unified diff between two references."""
        return self.repo.git.diff(ref_a, ref_b)

    def get_changed_files(self, staged: bool = True) -> list[Path]:
        """Return list of changed file paths."""
        if staged:
            diff_index = self.repo.index.diff("HEAD")
        else:
            diff_index = self.repo.index.diff(None)

        paths: list[Path] = []
        for diff_item in diff_index:
            if diff_item.a_path:
                paths.append(Path(diff_item.a_path))
            if diff_item.b_path and diff_item.b_path != diff_item.a_path:
                paths.append(Path(diff_item.b_path))
        return paths

    def get_current_branch(self) -> str:
        """Return the name of the current branch."""
        return str(self.repo.active_branch)

    def get_head_commit_sha(self) -> str:
        """Return the SHA of the HEAD commit."""
        return str(self.repo.head.commit.hexsha)

    def is_dirty(self) -> bool:
        """Check if the working directory has uncommitted changes."""
        return self.repo.is_dirty(untracked_files=True)
