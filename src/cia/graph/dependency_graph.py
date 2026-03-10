"""Module-level dependency graph construction and querying."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from cia.parser.base import ParsedModule


class DependencyGraph:
    """Directed graph representing module-level import dependencies."""

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX directed graph."""
        return self._graph

    def build_from_modules(self, modules: list[ParsedModule]) -> None:
        """Build the dependency graph from a list of parsed modules."""
        for module in modules:
            self._graph.add_node(
                module.module_name,
                file_path=str(module.file_path),
            )

        module_names = {m.module_name for m in modules}
        for module in modules:
            for imp in module.imports:
                target = imp.split(".")[0]
                if target in module_names:
                    self._graph.add_edge(module.module_name, target)

    def get_dependents(self, module_name: str) -> set[str]:
        """Return all modules that depend on the given module (reverse deps)."""
        if module_name not in self._graph:
            return set()
        return set(self._graph.predecessors(module_name))

    def get_dependencies(self, module_name: str) -> set[str]:
        """Return all modules that the given module depends on."""
        if module_name not in self._graph:
            return set()
        return set(self._graph.successors(module_name))

    def get_transitive_dependents(self, module_name: str) -> set[str]:
        """Return all modules transitively affected by changes to the given module."""
        if module_name not in self._graph:
            return set()
        ancestors = nx.ancestors(self._graph.reverse(), module_name)
        ancestors.discard(module_name)
        return ancestors

    def get_all_modules(self) -> list[str]:
        """Return all module names in the graph."""
        return list(self._graph.nodes)

    def to_dict(self) -> dict[str, list[str]]:
        """Export the graph as an adjacency dict."""
        return {
            node: list(self._graph.successors(node))
            for node in self._graph.nodes
        }
