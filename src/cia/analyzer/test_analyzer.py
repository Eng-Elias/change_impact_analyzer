"""Test impact prediction — discover tests, map to code, predict affected tests."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cia.graph.dependency_graph import DependencyGraph


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CodeTestMapping:
    """Maps a single test file to the production modules it exercises."""

    test_file: Path
    covered_modules: list[str] = field(default_factory=list)
    imported_modules: list[str] = field(default_factory=list)
    called_functions: list[str] = field(default_factory=list)


@dataclass
class MissingTestSuggestion:
    """A suggestion for a missing test."""

    entity: str
    reason: str
    suggested_file: str


# ---------------------------------------------------------------------------
# TestAnalyzer
# ---------------------------------------------------------------------------


_TEST_PATTERN = re.compile(r"(?:^|/)test_[^/]+\.py$|(?:^|/)tests?\.py$")


class TestAnalyzer:
    """Discovers tests, maps them to production code, and predicts impact."""

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @staticmethod
    def discover_tests(project_root: Path | str) -> list[Path]:
        """Recursively find all test files under *project_root*.

        A file is considered a test file when its name matches common
        conventions:
        - ``test_*.py``
        - ``*_test.py``
        - ``tests.py`` / ``test.py``

        Directories named ``__pycache__``, ``.git``, ``.tox``, and
        ``node_modules`` are skipped.
        """
        root = Path(project_root)
        skip_dirs = {"__pycache__", ".git", ".tox", "node_modules", ".venv", "venv"}
        results: list[Path] = []
        for path in sorted(root.rglob("*.py")):
            if any(part in skip_dirs for part in path.parts):
                continue
            name = path.name
            if (
                name.startswith("test_")
                or name.endswith("_test.py")
                or name in ("tests.py", "test.py")
            ):
                results.append(path)
        return results

    # ------------------------------------------------------------------
    # Mapping strategies
    # ------------------------------------------------------------------

    def map_tests_to_code(
        self,
        test_file: Path,
        graph: DependencyGraph | None = None,
    ) -> CodeTestMapping:
        """Build a *TestMapping* for a single test file.

        Uses multiple strategies:
        1. **Naming convention** — ``test_module.py`` ↔ ``module.py``
        2. **Import analysis** — modules imported by the test file
        3. **Function calls** — functions invoked in the test body
        """
        mapping = CodeTestMapping(test_file=test_file)

        # Strategy 1: naming convention
        conv_module = self._module_from_naming(test_file)
        if conv_module:
            mapping.covered_modules.append(conv_module)

        # Strategy 2 + 3: import & call analysis
        if test_file.exists():
            try:
                source = test_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(test_file))
            except (SyntaxError, UnicodeDecodeError):
                return mapping

            imports = self._extract_imports(tree)
            mapping.imported_modules = imports

            calls = self._extract_calls(tree)
            mapping.called_functions = calls

            # Add imported module stems to covered_modules
            for imp in imports:
                stem = imp.split(".")[0]
                if stem not in mapping.covered_modules:
                    mapping.covered_modules.append(stem)
                # Also add the leaf module name for dotted imports
                # e.g. "flags.flag_definition" → also add "flag_definition"
                leaf = imp.rsplit(".", maxsplit=1)[-1]
                if leaf != stem and leaf not in mapping.covered_modules:
                    mapping.covered_modules.append(leaf)

        return mapping

    def build_test_mapping(
        self,
        project_root: Path | str,
        graph: DependencyGraph | None = None,
    ) -> dict[Path, CodeTestMapping]:
        """Discover all tests and build mappings for the entire project."""
        tests = self.discover_tests(project_root)
        return {t: self.map_tests_to_code(t, graph) for t in tests}

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    @staticmethod
    def predict_affected_tests(
        changed_entities: list[str],
        test_mapping: dict[Path, CodeTestMapping],
    ) -> list[Path]:
        """Return test files that exercise any of *changed_entities*.

        *changed_entities* is a list of module names (stems) or
        qualified function names.
        """
        affected: list[Path] = []
        entity_set = set(changed_entities)

        for test_file, mapping in test_mapping.items():
            hit = False
            for module in mapping.covered_modules:
                if module in entity_set:
                    hit = True
                    break
            if not hit:
                for imp in mapping.imported_modules:
                    stem = imp.split(".")[0]
                    if stem in entity_set or imp in entity_set:
                        hit = True
                        break
            if not hit:
                for call in mapping.called_functions:
                    if call in entity_set:
                        hit = True
                        break
            if hit:
                affected.append(test_file)

        return affected

    # ------------------------------------------------------------------
    # Missing test suggestions
    # ------------------------------------------------------------------

    @staticmethod
    def suggest_missing_tests(
        changed_entities: list[str],
        existing_coverage: dict[str, float] | None = None,
        test_mapping: dict[Path, CodeTestMapping] | None = None,
        changed_symbols: list[dict[str, str]] | None = None,
    ) -> list[MissingTestSuggestion]:
        """Identify entities that lack test coverage and suggest new tests.

        Parameters
        ----------
        changed_entities:
            Module names or qualified symbol names that were changed.
        existing_coverage:
            Optional mapping of module stem → coverage % (0–100).
        test_mapping:
            Optional mapping of test files to *TestMapping*; used to
            check whether a module is already covered by at least one
            test.
        changed_symbols:
            Optional list of dicts with keys ``module``, ``name``,
            ``qualified_name``, and ``symbol_type``.  When a module
            already has test coverage but a specific symbol is never
            called in any test, a method-level suggestion is emitted.
        """
        coverage = existing_coverage or {}
        mapping = test_mapping or {}

        # Build set of covered modules from mapping
        covered_modules: set[str] = set()
        for m in mapping.values():
            covered_modules.update(m.covered_modules)

        suggestions: list[MissingTestSuggestion] = []
        for entity in changed_entities:
            stem = entity.split(".")[-1] if "." in entity else entity

            cov = coverage.get(stem)
            is_covered_by_tests = stem in covered_modules

            if cov is not None and cov < 50:
                suggestions.append(
                    MissingTestSuggestion(
                        entity=entity,
                        reason=f"Low test coverage ({cov:.0f}%)",
                        suggested_file=f"tests/test_{stem}.py",
                    )
                )
            elif cov is None and not is_covered_by_tests:
                suggestions.append(
                    MissingTestSuggestion(
                        entity=entity,
                        reason="No test coverage detected",
                        suggested_file=f"tests/test_{stem}.py",
                    )
                )

        # Symbol-level suggestions for covered modules
        if changed_symbols and mapping:
            all_test_calls: set[str] = set()
            for m in mapping.values():
                all_test_calls.update(m.called_functions)

            already_suggested: set[str] = {s.entity for s in suggestions}
            for sym in changed_symbols:
                module = sym.get("module", "")
                name = sym.get("name", "")
                qualified = sym.get("qualified_name", f"{module}::{name}")
                symbol_type = sym.get("symbol_type", "function")
                if not name or qualified in already_suggested:
                    continue
                # Only suggest if the module IS covered (otherwise the
                # module-level suggestion above already covers it).
                if module in covered_modules and name not in all_test_calls:
                    suggestions.append(
                        MissingTestSuggestion(
                            entity=qualified,
                            reason=f"New {symbol_type} with no test coverage",
                            suggested_file=f"tests/test_{module}.py",
                        )
                    )

        return suggestions

    # ------------------------------------------------------------------
    # Pytest integration
    # ------------------------------------------------------------------

    @staticmethod
    def generate_pytest_expression(test_files: list[Path]) -> str:
        """Generate a pytest ``-k`` selection expression for *test_files*.

        Returns a string like ``"test_foo or test_bar"`` suitable for::

            pytest -k "test_foo or test_bar"
        """
        if not test_files:
            return ""
        stems = list(dict.fromkeys(p.stem for p in test_files))
        return " or ".join(stems)

    @staticmethod
    def generate_pytest_args(test_files: list[Path]) -> list[str]:
        """Return a list of pytest CLI arguments to run only *test_files*."""
        return [str(f) for f in test_files]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _module_from_naming(test_file: Path) -> str | None:
        """Derive the production module name from a test file name."""
        name = test_file.stem
        if name.startswith("test_"):
            return name[5:]
        if name.endswith("_test"):
            return name[:-5]
        return None

    @staticmethod
    def _extract_imports(tree: ast.AST) -> list[str]:
        """Extract imported module names from an AST."""
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        return modules

    @staticmethod
    def _extract_calls(tree: ast.AST) -> list[str]:
        """Extract function call names from an AST."""
        calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)
        return calls
