"""Function/method-level call graph construction and querying."""

from __future__ import annotations

import json
from typing import Any

import networkx as nx

from cia.parser.base import ParsedModule, Symbol


class CallGraph:
    """Directed graph representing function/method call relationships.

    Each **node** is a qualified function name (``module.func`` or
    ``module.Class.method``) with metadata such as *module*,
    *line_start*, *line_end*.  Each **edge** is a call from *caller*
    to *callee* with an optional *line_number*.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX directed graph."""
        return self._graph

    @property
    def function_count(self) -> int:
        """Return the number of function nodes in the graph."""
        return int(self._graph.number_of_nodes())

    @property
    def call_count(self) -> int:
        """Return the number of call edges in the graph."""
        return int(self._graph.number_of_edges())

    # ------------------------------------------------------------------
    # Mutation — manual node / edge API
    # ------------------------------------------------------------------

    def add_function(
        self,
        module: str,
        function_name: str,
        line_start: int = 0,
        line_end: int = 0,
        *,
        file_path: str | None = None,
        symbol_type: str = "function",
    ) -> str:
        """Add a function node and return its qualified name.

        The qualified name is ``module.function_name``.
        """
        qualified = f"{module}.{function_name}"
        self._graph.add_node(
            qualified,
            module=module,
            function_name=function_name,
            symbol_type=symbol_type,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
        )
        return qualified

    def add_call(
        self,
        caller: str,
        callee: str,
        line_number: int = 0,
    ) -> None:
        """Add a call edge from *caller* to *callee*.

        Both *caller* and *callee* must be qualified names.  If a node
        does not yet exist it is created with minimal metadata.
        """
        for name in (caller, callee):
            if name not in self._graph:
                self._graph.add_node(name)
        self._graph.add_edge(caller, callee, line_number=line_number)

    # ------------------------------------------------------------------
    # Batch build from parsed modules
    # ------------------------------------------------------------------

    def build_from_modules(self, modules: list[ParsedModule]) -> None:
        """Build the call graph from a list of *ParsedModule* objects.

        Every function, method, and class symbol becomes a node.
        Call dependencies are resolved by matching short names to
        qualified names across all modules.
        """
        symbol_map: dict[str, Symbol] = {}

        for module in modules:
            for symbol in module.symbols:
                if symbol.symbol_type == "variable":
                    continue
                self._graph.add_node(
                    symbol.qualified_name,
                    module=module.module_name,
                    function_name=symbol.name,
                    symbol_type=symbol.symbol_type,
                    file_path=str(symbol.file_path),
                    line_start=symbol.line_start,
                    line_end=symbol.line_end,
                )
                symbol_map[symbol.name] = symbol

        for module in modules:
            for symbol in module.symbols:
                if symbol.symbol_type == "variable":
                    continue
                for dep_name in symbol.dependencies:
                    if dep_name in symbol_map:
                        target = symbol_map[dep_name]
                        self._graph.add_edge(
                            symbol.qualified_name,
                            target.qualified_name,
                        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_callers(self, qualified_name: str) -> set[str]:
        """Return all symbols that directly call *qualified_name*."""
        if qualified_name not in self._graph:
            return set()
        return set(self._graph.predecessors(qualified_name))

    def get_callees(self, qualified_name: str) -> set[str]:
        """Return all symbols directly called by *qualified_name*."""
        if qualified_name not in self._graph:
            return set()
        return set(self._graph.successors(qualified_name))

    def get_transitive_callers(self, qualified_name: str) -> set[str]:
        """Return all symbols that transitively call *qualified_name*."""
        if qualified_name not in self._graph:
            return set()
        return set(nx.ancestors(self._graph, qualified_name))

    def get_transitive_callees(self, qualified_name: str) -> set[str]:
        """Return all symbols transitively called by *qualified_name*."""
        if qualified_name not in self._graph:
            return set()
        return set(nx.descendants(self._graph, qualified_name))

    # ------------------------------------------------------------------
    # Dead code detection
    # ------------------------------------------------------------------

    def find_unreachable_functions(self) -> set[str]:
        """Return function nodes that have **no callers** (potential dead code).

        A node is considered unreachable if its in-degree is 0, meaning
        nothing in the graph calls it.
        """
        return {
            node
            for node, deg in self._graph.in_degree()
            if deg == 0
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize the call graph to a JSON string."""
        data: dict[str, Any] = {
            "functions": {},
            "calls": [],
        }
        for node, attrs in self._graph.nodes(data=True):
            data["functions"][node] = {
                "module": attrs.get("module"),
                "function_name": attrs.get("function_name"),
                "symbol_type": attrs.get("symbol_type"),
                "file_path": attrs.get("file_path"),
                "line_start": attrs.get("line_start", 0),
                "line_end": attrs.get("line_end", 0),
            }
        for src, dst, attrs in self._graph.edges(data=True):
            data["calls"].append(
                {
                    "caller": src,
                    "callee": dst,
                    "line_number": attrs.get("line_number", 0),
                }
            )
        return json.dumps(data, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> CallGraph:
        """Deserialize a call graph from a JSON string produced by :meth:`to_json`."""
        data = json.loads(json_str)
        cg = cls()
        for qname, attrs in data.get("functions", {}).items():
            mod = attrs.get("module") or ""
            fname = attrs.get("function_name") or qname.rsplit(".", 1)[-1]
            cg.add_function(
                module=mod,
                function_name=fname,
                line_start=attrs.get("line_start", 0),
                line_end=attrs.get("line_end", 0),
                file_path=attrs.get("file_path"),
                symbol_type=attrs.get("symbol_type", "function"),
            )
        for edge in data.get("calls", []):
            cg.add_call(
                caller=edge["caller"],
                callee=edge["callee"],
                line_number=edge.get("line_number", 0),
            )
        return cg

    def to_dict(self) -> dict[str, list[str]]:
        """Export the call graph as a simple adjacency dict."""
        return {
            node: list(self._graph.successors(node))
            for node in self._graph.nodes
        }
