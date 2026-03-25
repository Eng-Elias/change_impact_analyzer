"""Module-level dependency graph construction and querying."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from cia.parser.base import ParsedModule


class DependencyGraph:
    """Directed graph representing module-level import dependencies.

    Each **node** is a module name (``str``) with optional metadata
    (``file_path``, ``ast_data``).  Each **edge** represents an import
    dependency with optional ``dependency_type`` and ``line_number``
    attributes.
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
    def module_count(self) -> int:
        """Return the number of modules in the graph."""
        return int(self._graph.number_of_nodes())

    @property
    def dependency_count(self) -> int:
        """Return the number of dependency edges in the graph."""
        return int(self._graph.number_of_edges())

    # ------------------------------------------------------------------
    # Mutation — manual node / edge API
    # ------------------------------------------------------------------

    def add_module(
        self,
        name: str,
        filepath: str | Path | None = None,
        ast_data: Any = None,
    ) -> None:
        """Add a module node to the graph.

        Parameters
        ----------
        name:
            Unique module name used as the graph node key.
        filepath:
            Optional file-system path for the module.
        ast_data:
            Optional arbitrary data to attach (e.g. AST reference).
        """
        self._graph.add_node(
            name,
            file_path=str(filepath) if filepath else None,
            ast_data=ast_data,
        )

    def add_dependency(
        self,
        from_module: str,
        to_module: str,
        dependency_type: str = "import",
        line_number: int = 0,
    ) -> None:
        """Add a directed dependency edge *from_module* → *to_module*.

        Parameters
        ----------
        from_module:
            The module that contains the import.
        to_module:
            The module being imported.
        dependency_type:
            Category of the dependency (``"import"``, ``"re-export"``, …).
        line_number:
            Source line where the import appears.
        """
        for mod in (from_module, to_module):
            if mod not in self._graph:
                self._graph.add_node(mod)
        self._graph.add_edge(
            from_module,
            to_module,
            dependency_type=dependency_type,
            line_number=line_number,
        )

    # ------------------------------------------------------------------
    # Batch build from parsed modules
    # ------------------------------------------------------------------

    def build_from_modules(self, modules: list[ParsedModule]) -> None:
        """Build the dependency graph from a list of *ParsedModule* objects.

        Nodes are created for every module.  Edges are created for every
        import whose top-level *or leaf* name matches an existing module
        node.  This handles both flat layouts (``import flag_definition``)
        and package layouts (``from flags.flag_definition import …``).
        """
        for module in modules:
            self.add_module(module.module_name, filepath=module.file_path)

        module_names = {m.module_name for m in modules}
        for module in modules:
            for imp in module.imports:
                if not imp.module:
                    continue
                parts = imp.module.split(".")
                # Try every segment: top-level first, then leaf, then
                # intermediate segments — first match wins.
                target: str | None = None
                if parts[0] in module_names:
                    target = parts[0]
                elif len(parts) > 1 and parts[-1] in module_names:
                    target = parts[-1]
                else:
                    for seg in parts[1:-1]:
                        if seg in module_names:
                            target = seg
                            break
                if target and target != module.module_name:
                    self.add_dependency(
                        from_module=module.module_name,
                        to_module=target,
                        dependency_type="import",
                        line_number=imp.line_number,
                    )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_dependencies(self, module_name: str) -> list[str]:
        """Return modules that *module_name* depends on (direct successors)."""
        if module_name not in self._graph:
            return []
        return list(self._graph.successors(module_name))

    def get_dependents(self, module_name: str) -> list[str]:
        """Return modules that depend on *module_name* (direct predecessors)."""
        if module_name not in self._graph:
            return []
        return list(self._graph.predecessors(module_name))

    def get_transitive_dependencies(self, module_name: str) -> set[str]:
        """Return the full set of modules that *module_name* transitively depends on."""
        if module_name not in self._graph:
            return set()
        return set(nx.descendants(self._graph, module_name))

    def get_transitive_dependents(self, module_name: str) -> set[str]:
        """Return all modules transitively affected by changes to *module_name*."""
        if module_name not in self._graph:
            return set()
        return set(nx.ancestors(self._graph, module_name))

    def get_all_modules(self) -> list[str]:
        """Return all module names in the graph."""
        return list(self._graph.nodes)

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def find_cycles(self) -> list[list[str]]:
        """Detect circular dependencies and return them as lists of module names.

        Each returned list is a cycle, e.g. ``["a", "b", "a"]``.
        """
        try:
            cycles = list(nx.simple_cycles(self._graph))
        except nx.NetworkXError:
            return []
        return [list(c) for c in cycles]

    def has_cycles(self) -> bool:
        """Return ``True`` if the graph contains at least one cycle."""
        return not nx.is_directed_acyclic_graph(self._graph)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize the graph to a JSON string."""
        data: dict[str, Any] = {
            "modules": {},
            "dependencies": [],
        }
        for node, attrs in self._graph.nodes(data=True):
            data["modules"][node] = {
                "file_path": attrs.get("file_path"),
            }
        for src, dst, attrs in self._graph.edges(data=True):
            data["dependencies"].append(
                {
                    "from": src,
                    "to": dst,
                    "type": attrs.get("dependency_type", "import"),
                    "line_number": attrs.get("line_number", 0),
                }
            )
        return json.dumps(data, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> DependencyGraph:
        """Deserialize a graph from a JSON string produced by :meth:`to_json`."""
        data = json.loads(json_str)
        graph = cls()
        for name, attrs in data.get("modules", {}).items():
            graph.add_module(name, filepath=attrs.get("file_path"))
        for edge in data.get("dependencies", []):
            graph.add_dependency(
                from_module=edge["from"],
                to_module=edge["to"],
                dependency_type=edge.get("type", "import"),
                line_number=edge.get("line_number", 0),
            )
        return graph

    def to_dict(self) -> dict[str, list[str]]:
        """Export the graph as a simple adjacency dict."""
        return {
            node: list(self._graph.successors(node))
            for node in self._graph.nodes
        }
