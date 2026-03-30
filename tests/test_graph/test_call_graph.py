"""Comprehensive tests for CallGraph."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cia.graph.call_graph import CallGraph
from cia.parser.base import ParsedModule, Symbol

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def empty_cg() -> CallGraph:
    return CallGraph()


@pytest.fixture
def simple_cg() -> CallGraph:
    """main → helper → compute (linear call chain)."""
    cg = CallGraph()
    cg.add_function("app", "main", line_start=1, line_end=5)
    cg.add_function("app", "helper", line_start=7, line_end=10)
    cg.add_function("utils", "compute", line_start=1, line_end=3)
    cg.add_call("app.main", "app.helper")
    cg.add_call("app.helper", "utils.compute")
    return cg


@pytest.fixture
def diamond_cg() -> CallGraph:
    """A calls B and C; B and C both call D."""
    cg = CallGraph()
    for mod, fn in [("m", "A"), ("m", "B"), ("m", "C"), ("m", "D")]:
        cg.add_function(mod, fn)
    cg.add_call("m.A", "m.B")
    cg.add_call("m.A", "m.C")
    cg.add_call("m.B", "m.D")
    cg.add_call("m.C", "m.D")
    return cg


def _make_module_with_symbols(
    name: str, symbols: list[tuple[str, str, list[str]]]
) -> ParsedModule:
    """Create a ParsedModule with symbols.

    *symbols* is a list of ``(symbol_name, symbol_type, deps)``.
    """
    syms = [
        Symbol(
            name=sname,
            qualified_name=f"{name}.{sname}",
            symbol_type=stype,
            file_path=Path(f"{name}.py"),
            line_start=i + 1,
            line_end=i + 3,
            dependencies=deps,
        )
        for i, (sname, stype, deps) in enumerate(symbols)
    ]
    return ParsedModule(
        file_path=Path(f"{name}.py"),
        module_name=name,
        symbols=syms,
    )


# ==================================================================
# Basic construction
# ==================================================================


class TestConstruction:
    """Test adding functions and calls."""

    def test_add_function(self, empty_cg: CallGraph) -> None:
        qn = empty_cg.add_function("mod", "foo", line_start=1, line_end=5)
        assert qn == "mod.foo"
        assert empty_cg.function_count == 1

    def test_add_function_metadata(self, empty_cg: CallGraph) -> None:
        empty_cg.add_function(
            "mod",
            "bar",
            line_start=10,
            line_end=20,
            file_path="mod.py",
            symbol_type="method",
        )
        attrs = empty_cg.graph.nodes["mod.bar"]
        assert attrs["module"] == "mod"
        assert attrs["function_name"] == "bar"
        assert attrs["symbol_type"] == "method"
        assert attrs["file_path"] == "mod.py"
        assert attrs["line_start"] == 10
        assert attrs["line_end"] == 20

    def test_add_call(self, empty_cg: CallGraph) -> None:
        empty_cg.add_function("m", "a")
        empty_cg.add_function("m", "b")
        empty_cg.add_call("m.a", "m.b", line_number=3)
        assert empty_cg.call_count == 1
        edge = empty_cg.graph.edges["m.a", "m.b"]
        assert edge["line_number"] == 3

    def test_add_call_auto_creates_nodes(self, empty_cg: CallGraph) -> None:
        empty_cg.add_call("x.foo", "y.bar")
        assert empty_cg.function_count == 2

    def test_function_count(self, simple_cg: CallGraph) -> None:
        assert simple_cg.function_count == 3

    def test_call_count(self, simple_cg: CallGraph) -> None:
        assert simple_cg.call_count == 2


# ==================================================================
# build_from_modules
# ==================================================================


class TestBuildFromModules:
    """Test batch building from parsed modules."""

    def test_build_simple(self) -> None:
        modules = [
            _make_module_with_symbols(
                "app",
                [
                    ("main", "function", ["helper"]),
                ],
            ),
            _make_module_with_symbols(
                "utils",
                [
                    ("helper", "function", []),
                ],
            ),
        ]
        cg = CallGraph()
        cg.build_from_modules(modules)
        assert cg.function_count == 2
        assert cg.call_count == 1
        assert cg.get_callees("app.main") == {"utils.helper"}

    def test_build_skips_variables(self) -> None:
        modules = [
            _make_module_with_symbols(
                "conf",
                [
                    ("DEBUG", "variable", []),
                    ("setup", "function", []),
                ],
            ),
        ]
        cg = CallGraph()
        cg.build_from_modules(modules)
        assert "conf.DEBUG" not in cg.graph
        assert "conf.setup" in cg.graph

    def test_build_methods(self) -> None:
        modules = [
            _make_module_with_symbols(
                "svc",
                [
                    ("Service", "class", []),
                    ("run", "method", ["helper"]),
                    ("helper", "function", []),
                ],
            ),
        ]
        cg = CallGraph()
        cg.build_from_modules(modules)
        assert cg.get_callees("svc.run") == {"svc.helper"}

    def test_build_from_sample_project(
        self, sample_parsed_modules: list[ParsedModule]
    ) -> None:
        cg = CallGraph()
        cg.build_from_modules(sample_parsed_modules)
        assert cg.function_count > 0


# ==================================================================
# Queries — callers / callees
# ==================================================================


class TestQueries:
    """Test caller and callee queries."""

    def test_get_callers(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_callers("app.helper") == {"app.main"}

    def test_get_callees(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_callees("app.main") == {"app.helper"}

    def test_get_callers_root(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_callers("app.main") == set()

    def test_get_callees_leaf(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_callees("utils.compute") == set()

    def test_missing_node_callers(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_callers("MISSING") == set()

    def test_missing_node_callees(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_callees("MISSING") == set()

    def test_diamond_callers(self, diamond_cg: CallGraph) -> None:
        assert diamond_cg.get_callers("m.D") == {"m.B", "m.C"}

    def test_diamond_callees(self, diamond_cg: CallGraph) -> None:
        assert diamond_cg.get_callees("m.A") == {"m.B", "m.C"}


# ==================================================================
# Transitive queries
# ==================================================================


class TestTransitive:
    """Test transitive caller / callee calculations."""

    def test_transitive_callers(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_transitive_callers("utils.compute") == {
            "app.main",
            "app.helper",
        }

    def test_transitive_callees(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_transitive_callees("app.main") == {
            "app.helper",
            "utils.compute",
        }

    def test_transitive_callers_root(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_transitive_callers("app.main") == set()

    def test_transitive_callees_leaf(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_transitive_callees("utils.compute") == set()

    def test_transitive_missing(self, simple_cg: CallGraph) -> None:
        assert simple_cg.get_transitive_callers("MISSING") == set()
        assert simple_cg.get_transitive_callees("MISSING") == set()

    def test_transitive_diamond(self, diamond_cg: CallGraph) -> None:
        assert diamond_cg.get_transitive_callers("m.D") == {"m.A", "m.B", "m.C"}
        assert diamond_cg.get_transitive_callees("m.A") == {"m.B", "m.C", "m.D"}


# ==================================================================
# Dead code / unreachable functions
# ==================================================================


class TestUnreachable:
    """Test dead code detection."""

    def test_unreachable_in_simple(self, simple_cg: CallGraph) -> None:
        unreachable = simple_cg.find_unreachable_functions()
        assert "app.main" in unreachable
        assert "app.helper" not in unreachable
        assert "utils.compute" not in unreachable

    def test_all_called(self) -> None:
        cg = CallGraph()
        cg.add_function("m", "a")
        cg.add_function("m", "b")
        cg.add_call("m.a", "m.b")
        cg.add_call("m.b", "m.a")
        assert cg.find_unreachable_functions() == set()

    def test_empty_graph(self, empty_cg: CallGraph) -> None:
        assert empty_cg.find_unreachable_functions() == set()

    def test_isolated_nodes_are_unreachable(self) -> None:
        cg = CallGraph()
        cg.add_function("m", "orphan")
        assert cg.find_unreachable_functions() == {"m.orphan"}

    def test_multiple_roots(self, diamond_cg: CallGraph) -> None:
        unreachable = diamond_cg.find_unreachable_functions()
        assert "m.A" in unreachable
        assert "m.D" not in unreachable


# ==================================================================
# Serialization
# ==================================================================


class TestSerialization:
    """Test JSON serialization / deserialization."""

    def test_to_json_valid(self, simple_cg: CallGraph) -> None:
        j = simple_cg.to_json()
        data = json.loads(j)
        assert "functions" in data
        assert "calls" in data
        assert len(data["functions"]) == 3
        assert len(data["calls"]) == 2

    def test_roundtrip(self, simple_cg: CallGraph) -> None:
        j = simple_cg.to_json()
        restored = CallGraph.from_json(j)
        assert restored.function_count == simple_cg.function_count
        assert restored.call_count == simple_cg.call_count
        assert restored.get_callees("app.main") == simple_cg.get_callees("app.main")

    def test_roundtrip_diamond(self, diamond_cg: CallGraph) -> None:
        j = diamond_cg.to_json()
        restored = CallGraph.from_json(j)
        assert restored.get_callers("m.D") == diamond_cg.get_callers("m.D")

    def test_roundtrip_preserves_metadata(self) -> None:
        cg = CallGraph()
        cg.add_function("mod", "func", line_start=10, line_end=20, file_path="mod.py")
        cg.add_function("mod", "other", line_start=22, line_end=30)
        cg.add_call("mod.func", "mod.other", line_number=15)
        restored = CallGraph.from_json(cg.to_json())
        attrs = restored.graph.nodes["mod.func"]
        assert attrs["line_start"] == 10
        assert attrs["line_end"] == 20
        assert attrs["file_path"] == "mod.py"

    def test_empty_roundtrip(self, empty_cg: CallGraph) -> None:
        restored = CallGraph.from_json(empty_cg.to_json())
        assert restored.function_count == 0

    def test_to_dict(self, simple_cg: CallGraph) -> None:
        d = simple_cg.to_dict()
        assert d["app.main"] == ["app.helper"]
        assert d["app.helper"] == ["utils.compute"]
        assert d["utils.compute"] == []
