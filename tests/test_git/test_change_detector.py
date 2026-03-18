"""Comprehensive tests for ChangeDetector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cia.analyzer.change_detector import Change, ChangeDetector, ChangeSet
from cia.graph.dependency_graph import DependencyGraph
from cia.parser.base import Symbol

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def detector() -> ChangeDetector:
    return ChangeDetector()


@pytest.fixture
def simple_diff() -> str:
    return (
        "diff --git a/utils.py b/utils.py\n"
        "index abc1234..def5678 100644\n"
        "--- a/utils.py\n"
        "+++ b/utils.py\n"
        "@@ -1,4 +1,5 @@\n"
        " def helper():\n"
        '-    return "help"\n'
        '+    return "updated help"\n'
        "+\n"
        " def compute(x):\n"
        "     return x * 2\n"
    )


@pytest.fixture
def multi_file_diff() -> str:
    return (
        "diff --git a/a.py b/a.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -1,2 +1,3 @@\n"
        " x = 1\n"
        "+y = 2\n"
        " z = 3\n"
        "diff --git a/b.py b/b.py\n"
        "index 3333333..4444444 100644\n"
        "--- a/b.py\n"
        "+++ b/b.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-old = True\n"
        "+new = True\n"
        " keep = True\n"
    )


@pytest.fixture
def new_file_diff() -> str:
    return (
        "diff --git a/new.py b/new.py\n"
        "new file mode 100644\n"
        "index 0000000..abcdef1\n"
        "--- /dev/null\n"
        "+++ b/new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+x = 1\n"
        "+y = 2\n"
    )


@pytest.fixture
def deleted_file_diff() -> str:
    return (
        "diff --git a/old.py b/old.py\n"
        "deleted file mode 100644\n"
        "index abcdef1..0000000\n"
        "--- a/old.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-x = 1\n"
        "-y = 2\n"
    )


@pytest.fixture
def renamed_file_diff() -> str:
    return (
        "diff --git a/old_name.py b/new_name.py\n"
        "similarity index 90%\n"
        "rename from old_name.py\n"
        "rename to new_name.py\n"
        "index abc..def 100644\n"
        "--- a/old_name.py\n"
        "+++ b/new_name.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-x = 1\n"
        "+x = 2\n"
        " y = 3\n"
    )


# ==================================================================
# parse_diff
# ==================================================================


class TestParseDiff:
    def test_simple_diff(self, detector: ChangeDetector, simple_diff: str) -> None:
        changes = detector.parse_diff(simple_diff)
        assert len(changes) == 1
        assert changes[0].file_path == Path("utils.py")
        assert changes[0].change_type == "modified"
        assert len(changes[0].added_lines) > 0

    def test_multi_file_diff(self, detector: ChangeDetector, multi_file_diff: str) -> None:
        changes = detector.parse_diff(multi_file_diff)
        assert len(changes) == 2
        paths = {c.file_path for c in changes}
        assert paths == {Path("a.py"), Path("b.py")}

    def test_new_file(self, detector: ChangeDetector, new_file_diff: str) -> None:
        changes = detector.parse_diff(new_file_diff)
        assert len(changes) == 1
        assert changes[0].change_type == "added"

    def test_deleted_file(self, detector: ChangeDetector, deleted_file_diff: str) -> None:
        changes = detector.parse_diff(deleted_file_diff)
        assert len(changes) == 1
        assert changes[0].change_type == "deleted"

    def test_renamed_file(self, detector: ChangeDetector, renamed_file_diff: str) -> None:
        changes = detector.parse_diff(renamed_file_diff)
        assert len(changes) == 1
        assert changes[0].change_type == "renamed"
        assert changes[0].old_path == Path("old_name.py")
        assert changes[0].file_path == Path("new_name.py")

    def test_empty_diff(self, detector: ChangeDetector) -> None:
        changes = detector.parse_diff("")
        assert changes == []

    def test_added_line_numbers(self, detector: ChangeDetector, simple_diff: str) -> None:
        changes = detector.parse_diff(simple_diff)
        assert 2 in changes[0].added_lines or 3 in changes[0].added_lines


# ==================================================================
# categorize_changes
# ==================================================================


class TestCategorize:
    def test_categorize_mixed(self, detector: ChangeDetector) -> None:
        changes = [
            Change(file_path=Path("a.py"), change_type="added"),
            Change(file_path=Path("b.py"), change_type="modified"),
            Change(file_path=Path("c.py"), change_type="deleted"),
            Change(file_path=Path("d.py"), change_type="renamed", old_path=Path("old_d.py")),
        ]
        added, modified, deleted, renamed = detector.categorize_changes(changes)
        assert added == [Path("a.py")]
        assert modified == [Path("b.py")]
        assert deleted == [Path("c.py")]
        assert renamed == [(Path("old_d.py"), Path("d.py"))]

    def test_categorize_empty(self, detector: ChangeDetector) -> None:
        added, modified, deleted, renamed = detector.categorize_changes([])
        assert added == modified == deleted == []
        assert renamed == []


# ==================================================================
# get_changed_lines
# ==================================================================


class TestGetChangedLines:
    def test_changed_lines_simple(self, detector: ChangeDetector, simple_diff: str) -> None:
        ranges = detector.get_changed_lines(simple_diff)
        assert len(ranges) >= 1
        assert all(isinstance(r, tuple) and len(r) == 2 for r in ranges)

    def test_changed_lines_empty(self, detector: ChangeDetector) -> None:
        assert detector.get_changed_lines("") == []

    def test_changed_lines_multi_hunk(self, detector: ChangeDetector) -> None:
        diff = (
            "diff --git a/f.py b/f.py\n"
            "--- a/f.py\n"
            "+++ b/f.py\n"
            "@@ -1,3 +1,4 @@\n"
            " a = 1\n"
            "+b = 2\n"
            " c = 3\n"
            " d = 4\n"
            "@@ -10,3 +11,4 @@\n"
            " e = 5\n"
            "+f = 6\n"
            " g = 7\n"
            " h = 8\n"
        )
        ranges = detector.get_changed_lines(diff)
        assert len(ranges) == 2


# ==================================================================
# detect_changes (via GitIntegration mock)
# ==================================================================


class TestDetectChanges:
    def test_detect_staged(self, detector: ChangeDetector, simple_diff: str) -> None:
        mock_git = MagicMock()
        mock_git.get_staged_diff.return_value = simple_diff
        cs = detector.detect_changes(mock_git, staged=True)
        assert isinstance(cs, ChangeSet)
        assert len(cs.changes) == 1
        mock_git.get_staged_diff.assert_called_once()

    def test_detect_unstaged(self, detector: ChangeDetector, simple_diff: str) -> None:
        mock_git = MagicMock()
        mock_git.get_unstaged_diff.return_value = simple_diff
        cs = detector.detect_changes(mock_git, staged=False)
        assert len(cs.changes) == 1
        mock_git.get_unstaged_diff.assert_called_once()

    def test_detect_changes_for_range(self, detector: ChangeDetector, simple_diff: str) -> None:
        mock_git = MagicMock()
        mock_git.get_diff_between.return_value = simple_diff
        cs = detector.detect_changes_for_range(mock_git, "HEAD~1..HEAD")
        assert len(cs.changes) == 1
        mock_git.get_diff_between.assert_called_once_with("HEAD~1", "HEAD")

    def test_invalid_commit_range(self, detector: ChangeDetector) -> None:
        mock_git = MagicMock()
        with pytest.raises(ValueError, match="Invalid commit range"):
            detector.detect_changes_for_range(mock_git, "INVALID")

    def test_changeset_categories(self, detector: ChangeDetector) -> None:
        diff = (
            "diff --git a/add.py b/add.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/add.py\n"
            "@@ -0,0 +1 @@\n"
            "+x = 1\n"
            "diff --git a/mod.py b/mod.py\n"
            "--- a/mod.py\n"
            "+++ b/mod.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        mock_git = MagicMock()
        mock_git.get_staged_diff.return_value = diff
        cs = detector.detect_changes(mock_git)
        assert Path("add.py") in cs.added
        assert Path("mod.py") in cs.modified


# ==================================================================
# map_changes_to_symbols
# ==================================================================


class TestMapToSymbols:
    def test_map_basic(self, detector: ChangeDetector) -> None:
        changes = [
            Change(
                file_path=Path("utils.py"),
                change_type="modified",
                added_lines=[2, 3],
            ),
        ]
        symbols = [
            Symbol(
                name="helper",
                qualified_name="utils.helper",
                symbol_type="function",
                file_path=Path("utils.py"),
                line_start=1,
                line_end=3,
            ),
            Symbol(
                name="compute",
                qualified_name="utils.compute",
                symbol_type="function",
                file_path=Path("utils.py"),
                line_start=5,
                line_end=7,
            ),
        ]
        result = detector.map_changes_to_symbols(changes, symbols)
        assert len(result[0].affected_symbols) == 1
        assert result[0].affected_symbols[0].name == "helper"

    def test_map_no_overlap(self, detector: ChangeDetector) -> None:
        changes = [
            Change(
                file_path=Path("utils.py"),
                change_type="modified",
                added_lines=[100],
            ),
        ]
        symbols = [
            Symbol(
                name="f",
                qualified_name="utils.f",
                symbol_type="function",
                file_path=Path("utils.py"),
                line_start=1,
                line_end=5,
            ),
        ]
        result = detector.map_changes_to_symbols(changes, symbols)
        assert result[0].affected_symbols == []


# ==================================================================
# map_changes_to_entities
# ==================================================================


class TestMapToEntities:
    def test_map_entities(self, detector: ChangeDetector) -> None:
        changes = [
            Change(file_path=Path("utils.py"), change_type="modified"),
        ]
        graph = DependencyGraph()
        graph.add_module("utils")
        graph.add_module("main")
        graph.add_dependency("main", "utils")
        result = detector.map_changes_to_entities(changes, graph)
        assert "utils" in result
        assert "main" in result["utils"]

    def test_map_entities_no_match(self, detector: ChangeDetector) -> None:
        changes = [
            Change(file_path=Path("unknown.py"), change_type="modified"),
        ]
        graph = DependencyGraph()
        graph.add_module("utils")
        result = detector.map_changes_to_entities(changes, graph)
        assert result == {}
