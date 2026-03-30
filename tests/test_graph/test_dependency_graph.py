"""Comprehensive tests for DependencyGraph."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cia.graph.dependency_graph import DependencyGraph
from cia.parser.base import Import, ParsedModule

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def empty_graph() -> DependencyGraph:
    return DependencyGraph()


@pytest.fixture
def linear_graph() -> DependencyGraph:
    """A → B → C (linear chain)."""
    g = DependencyGraph()
    g.add_module("A", filepath="a.py")
    g.add_module("B", filepath="b.py")
    g.add_module("C", filepath="c.py")
    g.add_dependency("A", "B")
    g.add_dependency("B", "C")
    return g


@pytest.fixture
def diamond_graph() -> DependencyGraph:
    """A → B, A → C, B → D, C → D (diamond)."""
    g = DependencyGraph()
    for name in ("A", "B", "C", "D"):
        g.add_module(name)
    g.add_dependency("A", "B")
    g.add_dependency("A", "C")
    g.add_dependency("B", "D")
    g.add_dependency("C", "D")
    return g


@pytest.fixture
def cyclic_graph() -> DependencyGraph:
    """A → B → C → A (cycle)."""
    g = DependencyGraph()
    for name in ("A", "B", "C"):
        g.add_module(name)
    g.add_dependency("A", "B")
    g.add_dependency("B", "C")
    g.add_dependency("C", "A")
    return g


def _make_parsed_module(name: str, import_modules: list[str]) -> ParsedModule:
    """Helper to create a ParsedModule with given imports."""
    imports = [
        Import(module=mod, line_number=i + 1) for i, mod in enumerate(import_modules)
    ]
    return ParsedModule(
        file_path=Path(f"{name}.py"),
        module_name=name,
        imports=imports,
    )


# ==================================================================
# Basic graph construction
# ==================================================================


class TestGraphConstruction:
    """Test adding modules and dependencies."""

    def test_add_module(self, empty_graph: DependencyGraph) -> None:
        empty_graph.add_module("foo", filepath="foo.py")
        assert empty_graph.module_count == 1
        assert "foo" in empty_graph.get_all_modules()

    def test_add_module_with_ast_data(self, empty_graph: DependencyGraph) -> None:
        empty_graph.add_module("bar", ast_data={"key": "value"})
        attrs = empty_graph.graph.nodes["bar"]
        assert attrs["ast_data"] == {"key": "value"}

    def test_add_dependency(self, empty_graph: DependencyGraph) -> None:
        empty_graph.add_module("a")
        empty_graph.add_module("b")
        empty_graph.add_dependency("a", "b", dependency_type="import", line_number=5)
        assert empty_graph.dependency_count == 1
        edge_data = empty_graph.graph.edges["a", "b"]
        assert edge_data["dependency_type"] == "import"
        assert edge_data["line_number"] == 5

    def test_add_dependency_auto_creates_nodes(
        self, empty_graph: DependencyGraph
    ) -> None:
        empty_graph.add_dependency("x", "y")
        assert empty_graph.module_count == 2
        assert set(empty_graph.get_all_modules()) == {"x", "y"}

    def test_module_count_property(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.module_count == 3

    def test_dependency_count_property(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.dependency_count == 2


# ==================================================================
# build_from_modules
# ==================================================================


class TestBuildFromModules:
    """Test building the graph from parsed modules."""

    def test_build_simple(self) -> None:
        modules = [
            _make_parsed_module("main", ["utils"]),
            _make_parsed_module("utils", []),
        ]
        g = DependencyGraph()
        g.build_from_modules(modules)
        assert g.module_count == 2
        assert g.get_dependencies("main") == ["utils"]

    def test_build_ignores_external(self) -> None:
        modules = [
            _make_parsed_module("app", ["os", "sys", "utils"]),
            _make_parsed_module("utils", []),
        ]
        g = DependencyGraph()
        g.build_from_modules(modules)
        assert g.get_dependencies("app") == ["utils"]

    def test_build_dotted_import(self) -> None:
        modules = [
            _make_parsed_module("client", ["utils.helpers"]),
            _make_parsed_module("utils", []),
        ]
        g = DependencyGraph()
        g.build_from_modules(modules)
        assert "utils" in g.get_dependencies("client")

    def test_build_from_parsed_modules_fixture(
        self, sample_parsed_modules: list[ParsedModule]
    ) -> None:
        g = DependencyGraph()
        g.build_from_modules(sample_parsed_modules)
        assert g.module_count > 0


# ==================================================================
# Queries — dependencies / dependents
# ==================================================================


class TestQueries:
    """Test dependency and dependent queries."""

    def test_get_dependencies_linear(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_dependencies("A") == ["B"]
        assert linear_graph.get_dependencies("B") == ["C"]
        assert linear_graph.get_dependencies("C") == []

    def test_get_dependents_linear(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_dependents("C") == ["B"]
        assert linear_graph.get_dependents("B") == ["A"]
        assert linear_graph.get_dependents("A") == []

    def test_get_dependencies_missing_node(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_dependencies("MISSING") == []

    def test_get_dependents_missing_node(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_dependents("MISSING") == []

    def test_get_dependencies_diamond(self, diamond_graph: DependencyGraph) -> None:
        deps = set(diamond_graph.get_dependencies("A"))
        assert deps == {"B", "C"}

    def test_get_dependents_diamond(self, diamond_graph: DependencyGraph) -> None:
        dependents = set(diamond_graph.get_dependents("D"))
        assert dependents == {"B", "C"}


# ==================================================================
# Transitive queries
# ==================================================================


class TestTransitive:
    """Test transitive dependency / dependent calculations."""

    def test_transitive_dependencies_linear(
        self, linear_graph: DependencyGraph
    ) -> None:
        assert linear_graph.get_transitive_dependencies("A") == {"B", "C"}

    def test_transitive_dependencies_leaf(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_transitive_dependencies("C") == set()

    def test_transitive_dependents_linear(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_transitive_dependents("C") == {"A", "B"}

    def test_transitive_dependents_root(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_transitive_dependents("A") == set()

    def test_transitive_dependencies_diamond(
        self, diamond_graph: DependencyGraph
    ) -> None:
        assert diamond_graph.get_transitive_dependencies("A") == {"B", "C", "D"}

    def test_transitive_dependents_diamond(
        self, diamond_graph: DependencyGraph
    ) -> None:
        assert diamond_graph.get_transitive_dependents("D") == {"A", "B", "C"}

    def test_transitive_missing_node(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.get_transitive_dependencies("MISSING") == set()
        assert linear_graph.get_transitive_dependents("MISSING") == set()


# ==================================================================
# Cycle detection
# ==================================================================


class TestCycleDetection:
    """Test circular dependency detection."""

    def test_no_cycles_linear(self, linear_graph: DependencyGraph) -> None:
        assert linear_graph.find_cycles() == []
        assert linear_graph.has_cycles() is False

    def test_no_cycles_diamond(self, diamond_graph: DependencyGraph) -> None:
        assert diamond_graph.find_cycles() == []
        assert diamond_graph.has_cycles() is False

    def test_has_cycle(self, cyclic_graph: DependencyGraph) -> None:
        assert cyclic_graph.has_cycles() is True
        cycles = cyclic_graph.find_cycles()
        assert len(cycles) >= 1
        cycle_nodes = set()
        for c in cycles:
            cycle_nodes.update(c)
        assert {"A", "B", "C"} <= cycle_nodes

    def test_empty_graph_no_cycles(self, empty_graph: DependencyGraph) -> None:
        assert empty_graph.has_cycles() is False
        assert empty_graph.find_cycles() == []

    def test_self_loop_cycle(self) -> None:
        g = DependencyGraph()
        g.add_module("self")
        g.add_dependency("self", "self")
        assert g.has_cycles() is True
        cycles = g.find_cycles()
        assert len(cycles) >= 1


# ==================================================================
# Serialization
# ==================================================================


class TestSerialization:
    """Test JSON serialization / deserialization."""

    def test_to_json_returns_valid_json(self, linear_graph: DependencyGraph) -> None:
        j = linear_graph.to_json()
        data = json.loads(j)
        assert "modules" in data
        assert "dependencies" in data

    def test_roundtrip(self, linear_graph: DependencyGraph) -> None:
        j = linear_graph.to_json()
        restored = DependencyGraph.from_json(j)
        assert restored.module_count == linear_graph.module_count
        assert restored.dependency_count == linear_graph.dependency_count
        assert set(restored.get_all_modules()) == set(linear_graph.get_all_modules())
        assert restored.get_dependencies("A") == linear_graph.get_dependencies("A")

    def test_roundtrip_diamond(self, diamond_graph: DependencyGraph) -> None:
        j = diamond_graph.to_json()
        restored = DependencyGraph.from_json(j)
        assert set(restored.get_dependencies("A")) == set(
            diamond_graph.get_dependencies("A")
        )
        assert set(restored.get_dependents("D")) == set(
            diamond_graph.get_dependents("D")
        )

    def test_roundtrip_preserves_edge_attrs(self) -> None:
        g = DependencyGraph()
        g.add_module("x", filepath="x.py")
        g.add_module("y", filepath="y.py")
        g.add_dependency("x", "y", dependency_type="re-export", line_number=42)
        restored = DependencyGraph.from_json(g.to_json())
        edge = restored.graph.edges["x", "y"]
        assert edge["dependency_type"] == "re-export"
        assert edge["line_number"] == 42

    def test_empty_graph_roundtrip(self, empty_graph: DependencyGraph) -> None:
        restored = DependencyGraph.from_json(empty_graph.to_json())
        assert restored.module_count == 0

    def test_to_dict(self, linear_graph: DependencyGraph) -> None:
        d = linear_graph.to_dict()
        assert d["A"] == ["B"]
        assert d["B"] == ["C"]
        assert d["C"] == []
