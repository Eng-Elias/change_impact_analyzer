"""Git hook management for automatic impact analysis."""

from __future__ import annotations

from pathlib import Path

PRE_COMMIT_HOOK_CONTENT = """\
#!/usr/bin/env python3
\"\"\"CIA pre-commit hook - runs impact analysis on staged changes.\"\"\"

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "cia", "analyze", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 and result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0  # Always allow commit; hook is informational


if __name__ == "__main__":
    raise SystemExit(main())
"""


class HookManager:
    """Manages installation and removal of Git hooks."""

    HOOK_NAME = "pre-commit-cia"

    def __init__(self, repo_path: str | Path) -> None:
        self._repo_path = Path(repo_path)
        self._hooks_dir = self._repo_path / ".git" / "hooks"

    @property
    def hook_path(self) -> Path:
        """Return the path to the CIA pre-commit hook."""
        return self._hooks_dir / "pre-commit"

    def install(self) -> Path:
        """Install the pre-commit hook. Returns the path to the installed hook."""
        if not self._hooks_dir.exists():
            raise FileNotFoundError(
                f"Git hooks directory not found: {self._hooks_dir}"
            )

        self.hook_path.write_text(PRE_COMMIT_HOOK_CONTENT, encoding="utf-8")
        self.hook_path.chmod(0o755)
        return self.hook_path

    def uninstall(self) -> bool:
        """Remove the pre-commit hook. Returns True if it was removed."""
        if self.hook_path.exists():
            content = self.hook_path.read_text(encoding="utf-8")
            if "cia" in content.lower():
                self.hook_path.unlink()
                return True
        return False

    def is_installed(self) -> bool:
        """Check if the CIA pre-commit hook is installed."""
        if not self.hook_path.exists():
            return False
        content = self.hook_path.read_text(encoding="utf-8")
        return "cia" in content.lower()
