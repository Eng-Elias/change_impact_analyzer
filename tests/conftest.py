"""Shared test fixtures for CIA test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.parser.base import ParsedModule, Symbol


@pytest.fixture
def sample_project_dir(tmp_path: Path) -> Path:
    """Create a temporary sample Python project for testing."""
    src = tmp_path / "sample"
    src.mkdir()

    (src / "__init__.py").write_text("", encoding="utf-8")

    (src / "main.py").write_text(
        'from sample import utils\n\ndef main():\n    utils.helper()\n\nif __name__ == "__main__":\n    main()\n',
        encoding="utf-8",
    )

    (src / "utils.py").write_text(
        'def helper():\n    return "help"\n\ndef compute(x):\n    return x * 2\n',
        encoding="utf-8",
    )

    (src / "models.py").write_text(
        "from sample.utils import compute\n\nclass Model:\n    def predict(self, x):\n        return compute(x)\n",
        encoding="utf-8",
    )

    return src


@pytest.fixture
def sample_parsed_modules(sample_project_dir: Path) -> list[ParsedModule]:
    """Return parsed modules from the sample project."""
    from cia.parser.python_parser import PythonParser

    parser = PythonParser()
    return parser.parse_directory(sample_project_dir)


@pytest.fixture
def sample_symbol() -> Symbol:
    """Return a sample Symbol for testing."""
    return Symbol(
        name="helper",
        qualified_name="utils.helper",
        symbol_type="function",
        file_path=Path("utils.py"),
        line_start=1,
        line_end=2,
        dependencies=[],
    )


@pytest.fixture
def sample_diff_text() -> str:
    """Return a sample unified diff for testing."""
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
