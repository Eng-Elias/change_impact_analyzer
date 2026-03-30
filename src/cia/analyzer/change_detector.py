"""Detection of code changes using Git diff information."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from cia.parser.base import Symbol

if TYPE_CHECKING:
    from cia.git.git_integration import GitIntegration
    from cia.graph.dependency_graph import DependencyGraph


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Change:
    """Represents a single change detected in the codebase."""

    file_path: Path
    change_type: str  # "added", "modified", "deleted", "renamed"
    old_path: Path | None = None
    added_lines: list[int] = field(default_factory=list)
    deleted_lines: list[int] = field(default_factory=list)
    affected_symbols: list[Symbol] = field(default_factory=list)


@dataclass
class ChangeSet:
    """Aggregated result of change detection."""

    changes: list[Change] = field(default_factory=list)
    added: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    renamed: list[tuple[Path, Path]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ChangeDetector
# ---------------------------------------------------------------------------

_HUNK_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class ChangeDetector:
    """Detects and categorises code changes from Git diffs."""

    # ------------------------------------------------------------------
    # High-level entry point
    # ------------------------------------------------------------------

    def detect_changes(
        self,
        git_integration: GitIntegration,
        *,
        staged: bool = True,
    ) -> ChangeSet:
        """Detect changes via *git_integration* and return a *ChangeSet*.

        Parameters
        ----------
        git_integration:
            An initialised :class:`GitIntegration` instance.
        staged:
            If ``True`` analyse staged changes, otherwise unstaged.
        """
        if staged:
            diff_text = git_integration.get_staged_diff()
        else:
            diff_text = git_integration.get_unstaged_diff()

        changes = self.parse_diff(diff_text)
        return self._build_changeset(changes)

    def detect_changes_for_range(
        self, git_integration: GitIntegration, commit_range: str
    ) -> ChangeSet:
        """Detect changes for a commit range (e.g. ``HEAD~3..HEAD``)."""
        parts = commit_range.split("..")
        if len(parts) != 2:
            raise ValueError(f"Invalid commit range: {commit_range!r}")
        diff_text = git_integration.get_diff_between(parts[0], parts[1])
        changes = self.parse_diff(diff_text)
        return self._build_changeset(changes)

    # ------------------------------------------------------------------
    # Diff parsing
    # ------------------------------------------------------------------

    def parse_diff(self, diff_text: str) -> list[Change]:
        """Parse a unified diff string and return a list of *Change* objects."""
        changes: list[Change] = []
        current_file: str | None = None
        change_type: str = "modified"
        old_path: str | None = None
        added_lines: list[int] = []
        deleted_lines: list[int] = []
        new_line = 0

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                if current_file is not None:
                    changes.append(
                        Change(
                            file_path=Path(current_file),
                            change_type=change_type,
                            old_path=Path(old_path) if old_path else None,
                            added_lines=added_lines,
                            deleted_lines=deleted_lines,
                        )
                    )
                parts = line.split(" b/")
                current_file = parts[-1] if len(parts) > 1 else None
                a_parts = line.split(" a/")
                old_path = a_parts[-1].split(" b/")[0] if len(a_parts) > 1 else None
                change_type = "modified"
                added_lines = []
                deleted_lines = []
                new_line = 0

            elif line.startswith("new file"):
                change_type = "added"

            elif line.startswith("deleted file"):
                change_type = "deleted"

            elif line.startswith("rename from"):
                change_type = "renamed"
                old_path = line.split("rename from ", 1)[-1]

            elif line.startswith("@@"):
                m = _HUNK_RE.search(line)
                if m:
                    new_line = int(m.group(2)) - 1

            elif line.startswith("+") and not line.startswith("+++"):
                new_line += 1
                added_lines.append(new_line)

            elif line.startswith("-") and not line.startswith("---"):
                deleted_lines.append(new_line + 1)

            else:
                new_line += 1

        if current_file is not None:
            changes.append(
                Change(
                    file_path=Path(current_file),
                    change_type=change_type,
                    old_path=Path(old_path) if old_path else None,
                    added_lines=added_lines,
                    deleted_lines=deleted_lines,
                )
            )

        return changes

    # ------------------------------------------------------------------
    # Categorisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def categorize_changes(
        files: list[Change],
    ) -> tuple[list[Path], list[Path], list[Path], list[tuple[Path, Path]]]:
        """Categorise changes into (added, modified, deleted, renamed)."""
        added: list[Path] = []
        modified: list[Path] = []
        deleted: list[Path] = []
        renamed: list[tuple[Path, Path]] = []
        for c in files:
            if c.change_type == "added":
                added.append(c.file_path)
            elif c.change_type == "deleted":
                deleted.append(c.file_path)
            elif c.change_type == "renamed":
                renamed.append((c.old_path or c.file_path, c.file_path))
            else:
                modified.append(c.file_path)
        return added, modified, deleted, renamed

    @staticmethod
    def get_changed_lines(diff_text: str) -> list[tuple[int, int]]:
        """Extract changed line-number ranges from a unified diff.

        Returns a list of ``(start, end)`` tuples for each hunk's
        **new-file** side.
        """
        ranges: list[tuple[int, int]] = []
        for m in _HUNK_RE.finditer(diff_text):
            start = int(m.group(2))
            # rough: count added/context lines in hunk to find end
            ranges.append((start, start))

        # refine: walk hunks to find actual ranges
        if not ranges:
            return ranges

        refined: list[tuple[int, int]] = []
        hunks = re.split(r"(?=^@@)", diff_text, flags=re.MULTILINE)
        for hunk in hunks:
            match = _HUNK_RE.search(hunk)
            if not match:
                continue
            start = int(match.group(2))
            cur = start - 1
            end = start
            for line in hunk.splitlines()[1:]:
                if line.startswith("+") and not line.startswith("+++"):
                    cur += 1
                    end = cur
                elif line.startswith("-") and not line.startswith("---"):
                    pass
                else:
                    cur += 1
            if end >= start:
                refined.append((start, end))
        return refined

    # ------------------------------------------------------------------
    # Entity mapping
    # ------------------------------------------------------------------

    def map_changes_to_symbols(
        self, changes: list[Change], symbols: list[Symbol]
    ) -> list[Change]:
        """Map detected changes to affected symbols based on line ranges."""
        symbols_by_file: dict[Path, list[Symbol]] = {}
        for symbol in symbols:
            symbols_by_file.setdefault(symbol.file_path, []).append(symbol)

        for change in changes:
            file_symbols = symbols_by_file.get(change.file_path, [])
            changed_lines = set(change.added_lines + change.deleted_lines)
            for symbol in file_symbols:
                symbol_lines = set(range(symbol.line_start, symbol.line_end + 1))
                if changed_lines & symbol_lines:
                    change.affected_symbols.append(symbol)

        return changes

    def map_changes_to_entities(
        self, changes: list[Change], graph: DependencyGraph
    ) -> dict[str, list[str]]:
        """Map changes to graph entities (modules that are affected).

        Returns a dict mapping each changed module name to the list of
        downstream modules that may be impacted.
        """
        impacted: dict[str, list[str]] = {}
        all_modules = set(graph.get_all_modules())
        for change in changes:
            module_name = change.file_path.stem
            if module_name in all_modules:
                dependents = graph.get_dependents(module_name)
                impacted[module_name] = list(dependents)
        return impacted

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_changeset(self, changes: list[Change]) -> ChangeSet:
        added, modified, deleted, renamed = self.categorize_changes(changes)
        return ChangeSet(
            changes=changes,
            added=added,
            modified=modified,
            deleted=deleted,
            renamed=renamed,
        )
