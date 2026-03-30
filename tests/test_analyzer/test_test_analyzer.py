"""Comprehensive tests for TestAnalyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.analyzer.test_analyzer import (
    CodeTestMapping,
    TestAnalyzer,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def analyzer() -> TestAnalyzer:
    return TestAnalyzer()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project layout with source + test files."""
    # Source files
    src = tmp_path / "src"
    src.mkdir()
    (src / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    (src / "models.py").write_text("class Model: pass\n", encoding="utf-8")
    (src / "core.py").write_text(
        "import utils\ndef run(): utils.helper()\n", encoding="utf-8"
    )

    # Test files
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_utils.py").write_text(
        "from src.utils import helper\ndef test_helper(): helper()\n",
        encoding="utf-8",
    )
    (tests / "test_models.py").write_text(
        "import src.models\ndef test_model(): pass\n",
        encoding="utf-8",
    )
    # A _test.py style file
    (tests / "core_test.py").write_text(
        "from src.core import run\ndef test_run(): run()\n",
        encoding="utf-8",
    )

    # A non-test Python file that should NOT be discovered
    (src / "conftest.py").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture
def mapping_fixture(
    project_dir: Path, analyzer: TestAnalyzer
) -> dict[Path, CodeTestMapping]:
    return analyzer.build_test_mapping(project_dir)


# ==================================================================
# Test discovery
# ==================================================================


class TestDiscoverTests:
    def test_finds_test_files(self, analyzer: TestAnalyzer, project_dir: Path) -> None:
        tests = analyzer.discover_tests(project_dir)
        names = {t.name for t in tests}
        assert "test_utils.py" in names
        assert "test_models.py" in names
        assert "core_test.py" in names

    def test_ignores_non_test_files(
        self, analyzer: TestAnalyzer, project_dir: Path
    ) -> None:
        tests = analyzer.discover_tests(project_dir)
        names = {t.name for t in tests}
        assert "utils.py" not in names
        assert "models.py" not in names

    def test_ignores_pycache(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "test_cached.py").write_text("", encoding="utf-8")
        tests = analyzer.discover_tests(tmp_path)
        assert len(tests) == 0

    def test_ignores_git_dir(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        git = tmp_path / ".git"
        git.mkdir()
        (git / "test_hook.py").write_text("", encoding="utf-8")
        tests = analyzer.discover_tests(tmp_path)
        assert len(tests) == 0

    def test_empty_project(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        assert analyzer.discover_tests(tmp_path) == []

    def test_discovers_tests_py(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        (tmp_path / "tests.py").write_text("pass\n", encoding="utf-8")
        tests = analyzer.discover_tests(tmp_path)
        assert len(tests) == 1
        assert tests[0].name == "tests.py"

    def test_discovers_test_py(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        (tmp_path / "test.py").write_text("pass\n", encoding="utf-8")
        tests = analyzer.discover_tests(tmp_path)
        assert len(tests) == 1

    def test_returns_sorted(self, analyzer: TestAnalyzer, project_dir: Path) -> None:
        tests = analyzer.discover_tests(project_dir)
        assert tests == sorted(tests)


# ==================================================================
# Test-to-code mapping
# ==================================================================


class TestMapTestsToCode:
    def test_naming_convention(self, analyzer: TestAnalyzer, project_dir: Path) -> None:
        test_file = project_dir / "tests" / "test_utils.py"
        mapping = analyzer.map_tests_to_code(test_file)
        assert "utils" in mapping.covered_modules

    def test_naming_convention_suffix(
        self, analyzer: TestAnalyzer, project_dir: Path
    ) -> None:
        test_file = project_dir / "tests" / "core_test.py"
        mapping = analyzer.map_tests_to_code(test_file)
        assert "core" in mapping.covered_modules

    def test_import_analysis(self, analyzer: TestAnalyzer, project_dir: Path) -> None:
        test_file = project_dir / "tests" / "test_utils.py"
        mapping = analyzer.map_tests_to_code(test_file)
        assert any("utils" in imp for imp in mapping.imported_modules)

    def test_call_analysis(self, analyzer: TestAnalyzer, project_dir: Path) -> None:
        test_file = project_dir / "tests" / "test_utils.py"
        mapping = analyzer.map_tests_to_code(test_file)
        assert "helper" in mapping.called_functions

    def test_nonexistent_file(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        mapping = analyzer.map_tests_to_code(tmp_path / "nonexistent.py")
        assert mapping.test_file == tmp_path / "nonexistent.py"
        assert mapping.imported_modules == []

    def test_syntax_error_file(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        bad = tmp_path / "test_bad.py"
        bad.write_text("def broken(:\n", encoding="utf-8")
        mapping = analyzer.map_tests_to_code(bad)
        assert mapping.imported_modules == []

    def test_no_naming_convention(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        f = tmp_path / "tests.py"
        f.write_text("import os\n", encoding="utf-8")
        mapping = analyzer.map_tests_to_code(f)
        # "tests" -> no naming match (tests.py doesn't match test_ or _test)
        assert "os" in mapping.imported_modules


# ==================================================================
# build_test_mapping
# ==================================================================


class TestBuildTestMapping:
    def test_builds_for_all_tests(
        self, mapping_fixture: dict, project_dir: Path
    ) -> None:
        names = {p.name for p in mapping_fixture}
        assert "test_utils.py" in names
        assert "test_models.py" in names
        assert "core_test.py" in names

    def test_values_are_test_mappings(self, mapping_fixture: dict) -> None:
        for v in mapping_fixture.values():
            assert isinstance(v, CodeTestMapping)


# ==================================================================
# Predict affected tests
# ==================================================================


class TestPredictAffectedTests:
    def test_module_match(self, analyzer: TestAnalyzer, mapping_fixture: dict) -> None:
        affected = analyzer.predict_affected_tests(["utils"], mapping_fixture)
        names = {t.name for t in affected}
        assert "test_utils.py" in names

    def test_multiple_modules(
        self, analyzer: TestAnalyzer, mapping_fixture: dict
    ) -> None:
        affected = analyzer.predict_affected_tests(["utils", "models"], mapping_fixture)
        names = {t.name for t in affected}
        assert "test_utils.py" in names
        assert "test_models.py" in names

    def test_no_match(self, analyzer: TestAnalyzer, mapping_fixture: dict) -> None:
        affected = analyzer.predict_affected_tests(["nonexistent"], mapping_fixture)
        assert affected == []

    def test_empty_entities(
        self, analyzer: TestAnalyzer, mapping_fixture: dict
    ) -> None:
        assert analyzer.predict_affected_tests([], mapping_fixture) == []

    def test_empty_mapping(self, analyzer: TestAnalyzer) -> None:
        assert analyzer.predict_affected_tests(["utils"], {}) == []

    def test_function_call_match(
        self, analyzer: TestAnalyzer, project_dir: Path
    ) -> None:
        test_file = project_dir / "tests" / "test_utils.py"
        mapping = {
            test_file: CodeTestMapping(
                test_file=test_file,
                covered_modules=[],
                imported_modules=[],
                called_functions=["helper"],
            )
        }
        affected = analyzer.predict_affected_tests(["helper"], mapping)
        assert test_file in affected

    def test_import_match(self, analyzer: TestAnalyzer, project_dir: Path) -> None:
        test_file = project_dir / "tests" / "test_utils.py"
        mapping = {
            test_file: CodeTestMapping(
                test_file=test_file,
                covered_modules=[],
                imported_modules=["src.utils"],
                called_functions=[],
            )
        }
        affected = analyzer.predict_affected_tests(["src.utils"], mapping)
        assert test_file in affected


# ==================================================================
# Suggest missing tests
# ==================================================================


class TestSuggestMissingTests:
    def test_no_coverage(self, analyzer: TestAnalyzer) -> None:
        suggestions = analyzer.suggest_missing_tests(["utils"])
        assert len(suggestions) == 1
        assert suggestions[0].entity == "utils"
        assert "No test coverage" in suggestions[0].reason

    def test_low_coverage(self, analyzer: TestAnalyzer) -> None:
        suggestions = analyzer.suggest_missing_tests(
            ["utils"], existing_coverage={"utils": 30.0}
        )
        assert len(suggestions) == 1
        assert "30%" in suggestions[0].reason

    def test_high_coverage_no_suggestion(self, analyzer: TestAnalyzer) -> None:
        suggestions = analyzer.suggest_missing_tests(
            ["utils"], existing_coverage={"utils": 90.0}
        )
        assert suggestions == []

    def test_covered_by_test_mapping(self, analyzer: TestAnalyzer) -> None:
        mapping = {
            Path("tests/test_utils.py"): CodeTestMapping(
                test_file=Path("tests/test_utils.py"),
                covered_modules=["utils"],
            )
        }
        suggestions = analyzer.suggest_missing_tests(["utils"], test_mapping=mapping)
        # utils is covered by test mapping → no suggestion
        assert suggestions == []

    def test_not_covered_by_mapping(self, analyzer: TestAnalyzer) -> None:
        mapping = {
            Path("tests/test_other.py"): CodeTestMapping(
                test_file=Path("tests/test_other.py"),
                covered_modules=["other"],
            )
        }
        suggestions = analyzer.suggest_missing_tests(["utils"], test_mapping=mapping)
        assert len(suggestions) == 1

    def test_suggested_file_name(self, analyzer: TestAnalyzer) -> None:
        suggestions = analyzer.suggest_missing_tests(["core"])
        assert suggestions[0].suggested_file == "tests/test_core.py"

    def test_empty_entities(self, analyzer: TestAnalyzer) -> None:
        assert analyzer.suggest_missing_tests([]) == []

    def test_qualified_name_entity(self, analyzer: TestAnalyzer) -> None:
        suggestions = analyzer.suggest_missing_tests(["pkg.module"])
        assert suggestions[0].suggested_file == "tests/test_module.py"


# ==================================================================
# Pytest integration
# ==================================================================


class TestPytestIntegration:
    def test_expression_single(self, analyzer: TestAnalyzer) -> None:
        expr = analyzer.generate_pytest_expression([Path("tests/test_foo.py")])
        assert expr == "test_foo"

    def test_expression_multiple(self, analyzer: TestAnalyzer) -> None:
        files = [Path("tests/test_foo.py"), Path("tests/test_bar.py")]
        expr = analyzer.generate_pytest_expression(files)
        assert "test_foo" in expr
        assert "test_bar" in expr
        assert " or " in expr

    def test_expression_empty(self, analyzer: TestAnalyzer) -> None:
        assert analyzer.generate_pytest_expression([]) == ""

    def test_expression_deduplicates(self, analyzer: TestAnalyzer) -> None:
        files = [Path("a/test_foo.py"), Path("b/test_foo.py")]
        expr = analyzer.generate_pytest_expression(files)
        assert expr.count("test_foo") == 1

    def test_args(self, analyzer: TestAnalyzer) -> None:
        files = [Path("tests/test_foo.py"), Path("tests/test_bar.py")]
        args = analyzer.generate_pytest_args(files)
        assert len(args) == 2
        assert all(isinstance(a, str) for a in args)

    def test_args_empty(self, analyzer: TestAnalyzer) -> None:
        assert analyzer.generate_pytest_args([]) == []


# ==================================================================
# Internal helpers
# ==================================================================


class TestInternalHelpers:
    def test_module_from_naming_prefix(self, analyzer: TestAnalyzer) -> None:
        assert analyzer._module_from_naming(Path("test_utils.py")) == "utils"

    def test_module_from_naming_suffix(self, analyzer: TestAnalyzer) -> None:
        assert analyzer._module_from_naming(Path("utils_test.py")) == "utils"

    def test_module_from_naming_no_match(self, analyzer: TestAnalyzer) -> None:
        assert analyzer._module_from_naming(Path("conftest.py")) is None

    def test_extract_imports(self, analyzer: TestAnalyzer, tmp_path: Path) -> None:
        import ast

        source = "import os\nfrom pathlib import Path\n"
        tree = ast.parse(source)
        imports = analyzer._extract_imports(tree)
        assert "os" in imports
        assert "pathlib" in imports

    def test_extract_calls(self, analyzer: TestAnalyzer) -> None:
        import ast

        source = "foo()\nbar.baz()\n"
        tree = ast.parse(source)
        calls = analyzer._extract_calls(tree)
        assert "foo" in calls
        assert "baz" in calls
