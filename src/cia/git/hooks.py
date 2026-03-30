"""Git hook management for automatic impact analysis."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Hook script template
# ---------------------------------------------------------------------------

_HOOK_TEMPLATE = '''\
#!{python_executable}
"""CIA pre-commit hook — runs impact analysis on staged changes."""

import json
import subprocess
import sys

BLOCK_THRESHOLD = "{block_threshold}"
PYTHON = r"{python_executable}"

RISK_ORDER = {{"none": 0, "low": 1, "medium": 2, "high": 3}}


def main() -> int:
    result = subprocess.run(
        [PYTHON, "-m", "cia", "analyze", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(result.stdout)
            return 0

        risk_data = report.get("risk", {{}})
        risk = risk_data.get("level", report.get("risk_level", "low"))
        print(result.stdout)

        threshold = RISK_ORDER.get(BLOCK_THRESHOLD, 0)
        level = RISK_ORDER.get(risk, 0)

        if threshold > 0 and level >= threshold:
            print(f"\\n[CIA] Commit BLOCKED — risk level: {{risk}}")
            return 1
        if risk == "medium":
            print(f"\\n[CIA] WARNING — risk level: {{risk}}")

    if result.returncode != 0 and result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_CIA_MARKER = "CIA pre-commit hook"


# ---------------------------------------------------------------------------
# HookManager
# ---------------------------------------------------------------------------


class HookManager:
    """Manages installation and removal of Git hooks.

    Supports configurable risk-based blocking:
    - ``"high"``   — block commits with high-risk changes
    - ``"medium"`` — block medium *and* high
    - ``"low"``    — block everything except ``"none"``
    - ``"none"``   — never block (informational only, the default)
    """

    HOOK_NAME = "pre-commit-cia"

    def __init__(self, repo_path: str | Path) -> None:
        self._repo_path = Path(repo_path)
        self._hooks_dir = self._repo_path / ".git" / "hooks"

    @property
    def hook_path(self) -> Path:
        """Return the path to the CIA pre-commit hook."""
        return self._hooks_dir / "pre-commit"

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------

    def install(self, *, block_threshold: str = "none") -> Path:
        """Install the pre-commit hook.

        Parameters
        ----------
        block_threshold:
            Risk level at or above which the hook will **block** the
            commit.  One of ``"high"``, ``"medium"``, ``"low"``, or
            ``"none"`` (default — never block).

        Returns the path to the installed hook file.
        """
        if not self._hooks_dir.exists():
            raise FileNotFoundError(f"Git hooks directory not found: {self._hooks_dir}")

        content = _HOOK_TEMPLATE.format(
            block_threshold=block_threshold,
            python_executable=sys.executable,
        )
        self.hook_path.write_text(content, encoding="utf-8")
        self.hook_path.chmod(self.hook_path.stat().st_mode | stat.S_IEXEC)
        return self.hook_path

    def uninstall(self) -> bool:
        """Remove the pre-commit hook.

        Only removes the hook if it was installed by CIA (contains the
        marker string).  Returns ``True`` if the hook was removed.
        """
        if self.hook_path.exists():
            content = self.hook_path.read_text(encoding="utf-8")
            if _CIA_MARKER in content:
                self.hook_path.unlink()
                return True
        return False

    def is_installed(self) -> bool:
        """Check if the CIA pre-commit hook is currently installed."""
        if not self.hook_path.exists():
            return False
        content = self.hook_path.read_text(encoding="utf-8")
        return _CIA_MARKER in content

    # ------------------------------------------------------------------
    # Analysis helpers (used by the hook script at runtime)
    # ------------------------------------------------------------------

    @staticmethod
    def run_analysis_on_staged() -> dict:
        """Run impact analysis on currently staged files.

        Returns a dict with ``"risk_level"`` and ``"details"`` keys.
        This is a convenience wrapper used by the hook script.
        """
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "cia", "analyze", "--format", "json"],
            capture_output=True,
            text=True,
        )
        import json

        try:
            return json.loads(result.stdout) if result.stdout else {}
        except json.JSONDecodeError:
            return {"error": result.stdout or result.stderr}

    @staticmethod
    def generate_pre_commit_report(analysis: dict) -> str:
        """Generate a human-readable report string from analysis results."""
        risk = analysis.get("risk_level", "unknown")
        lines = [f"CIA Impact Analysis — risk: {risk}"]
        for detail in analysis.get("details", []):
            lines.append(f"  - {detail}")
        return "\n".join(lines)
