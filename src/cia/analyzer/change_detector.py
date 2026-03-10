"""Detection of code changes using Git diff information."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cia.parser.base import Symbol


@dataclass
class Change:
    """Represents a single change detected in the codebase."""

    file_path: Path
    change_type: str  # "added", "modified", "deleted", "renamed"
    old_path: Path | None = None
    added_lines: list[int] = field(default_factory=list)
    deleted_lines: list[int] = field(default_factory=list)
    affected_symbols: list[Symbol] = field(default_factory=list)


class ChangeDetector:
    """Detects and categorises code changes from Git diffs."""

    def detect_changes(self, diff_text: str) -> list[Change]:
        """Parse a unified diff string and return a list of Change objects."""
        changes: list[Change] = []
        current_file: str | None = None
        added_lines: list[int] = []
        deleted_lines: list[int] = []
        current_line = 0

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                if current_file is not None:
                    changes.append(
                        Change(
                            file_path=Path(current_file),
                            change_type="modified",
                            added_lines=added_lines,
                            deleted_lines=deleted_lines,
                        )
                    )
                parts = line.split(" b/")
                current_file = parts[-1] if len(parts) > 1 else None
                added_lines = []
                deleted_lines = []
                current_line = 0

            elif line.startswith("@@"):
                hunk_header = line.split("@@")[1].strip() if "@@" in line[2:] else ""
                if hunk_header.startswith("+"):
                    try:
                        current_line = int(hunk_header.split(",")[0].lstrip("+")) - 1
                    except (ValueError, IndexError):
                        current_line = 0

            elif line.startswith("+") and not line.startswith("+++"):
                current_line += 1
                added_lines.append(current_line)

            elif line.startswith("-") and not line.startswith("---"):
                deleted_lines.append(current_line + 1)

            else:
                current_line += 1

        if current_file is not None:
            changes.append(
                Change(
                    file_path=Path(current_file),
                    change_type="modified",
                    added_lines=added_lines,
                    deleted_lines=deleted_lines,
                )
            )

        return changes

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
