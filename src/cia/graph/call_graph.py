"""Function/method-level call graph construction and querying."""

from __future__ import annotations

import networkx as nx

from cia.parser.base import ParsedModule, Symbol


class CallGraph:
    """Directed graph representing function/method call relationships."""

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX directed graph."""
        return self._graph

    def build_from_modules(self, modules: list[ParsedModule]) -> None:
        """Build the call graph from a list of parsed modules."""
        symbol_map: dict[str, Symbol] = {}

        for module in modules:
            for symbol in module.symbols:
                self._graph.add_node(
                    symbol.qualified_name,
                    symbol_type=symbol.symbol_type,
                    file_path=str(symbol.file_path),
                    line_start=symbol.line_start,
                    line_end=symbol.line_end,
                )
                symbol_map[symbol.name] = symbol

        for module in modules:
            for symbol in module.symbols:
                for dep_name in symbol.dependencies:
                    if dep_name in symbol_map:
                        target = symbol_map[dep_name]
                        self._graph.add_edge(
                            symbol.qualified_name,
                            target.qualified_name,
                        )

    def get_callers(self, qualified_name: str) -> set[str]:
        """Return all symbols that call the given symbol."""
        if qualified_name not in self._graph:
            return set()
        return set(self._graph.predecessors(qualified_name))

    def get_callees(self, qualified_name: str) -> set[str]:
        """Return all symbols called by the given symbol."""
        if qualified_name not in self._graph:
            return set()
        return set(self._graph.successors(qualified_name))

    def get_transitive_callers(self, qualified_name: str) -> set[str]:
        """Return all symbols transitively affected by changes to the given symbol."""
        if qualified_name not in self._graph:
            return set()
        ancestors = nx.ancestors(self._graph.reverse(), qualified_name)
        ancestors.discard(qualified_name)
        return ancestors

    def to_dict(self) -> dict[str, list[str]]:
        """Export the call graph as an adjacency dict."""
        return {
            node: list(self._graph.successors(node))
            for node in self._graph.nodes
        }
