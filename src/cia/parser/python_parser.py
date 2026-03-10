"""Python source code parser using astroid."""

from __future__ import annotations

from pathlib import Path

import astroid
from astroid import nodes

from cia.parser.base import BaseParser, ParsedModule, Symbol


class PythonParser(BaseParser):
    """Parser for Python source files using astroid."""

    def get_supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser supports."""
        return [".py"]

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a single Python file and extract symbols and dependencies."""
        module_name = file_path.stem
        parsed = ParsedModule(file_path=file_path, module_name=module_name)

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = astroid.parse(source, module_name=module_name)
        except astroid.exceptions.AstroidSyntaxError as exc:
            parsed.errors.append(f"Syntax error: {exc}")
            return parsed
        except Exception as exc:  # noqa: BLE001
            parsed.errors.append(f"Parse error: {exc}")
            return parsed

        parsed.imports = self._extract_imports(tree)
        parsed.symbols = self._extract_symbols(tree, file_path)
        return parsed

    def parse_directory(self, directory: Path) -> list[ParsedModule]:
        """Parse all Python files in a directory recursively."""
        results: list[ParsedModule] = []
        for ext in self.get_supported_extensions():
            for file_path in directory.rglob(f"*{ext}"):
                results.append(self.parse_file(file_path))
        return results

    def _extract_imports(self, tree: nodes.Module) -> list[str]:
        """Extract import statements from an AST."""
        imports: list[str] = []
        for node in tree.body:
            if isinstance(node, nodes.Import):
                for name, _ in node.names:
                    imports.append(name)
            elif isinstance(node, nodes.ImportFrom):
                module = node.modname or ""
                if module:
                    imports.append(module)
        return imports

    def _extract_symbols(self, tree: nodes.Module, file_path: Path) -> list[Symbol]:
        """Extract symbol definitions from an AST."""
        symbols: list[Symbol] = []

        for node in tree.body:
            if isinstance(node, nodes.FunctionDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        qualified_name=f"{tree.name}.{node.name}",
                        symbol_type="function",
                        file_path=file_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        dependencies=self._get_function_dependencies(node),
                    )
                )
            elif isinstance(node, nodes.ClassDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        qualified_name=f"{tree.name}.{node.name}",
                        symbol_type="class",
                        file_path=file_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        dependencies=self._get_class_dependencies(node),
                    )
                )
                for method in node.mymethods():
                    symbols.append(
                        Symbol(
                            name=method.name,
                            qualified_name=f"{tree.name}.{node.name}.{method.name}",
                            symbol_type="method",
                            file_path=file_path,
                            line_start=method.lineno,
                            line_end=method.end_lineno or method.lineno,
                            dependencies=self._get_function_dependencies(method),
                        )
                    )

        return symbols

    def _get_function_dependencies(self, node: nodes.FunctionDef) -> list[str]:
        """Extract names called or referenced within a function."""
        deps: list[str] = []
        for call_node in node.nodes_of_class(nodes.Call):
            if isinstance(call_node.func, nodes.Name):
                deps.append(call_node.func.name)
            elif isinstance(call_node.func, nodes.Attribute):
                deps.append(call_node.func.attrname)
        return list(set(deps))

    def _get_class_dependencies(self, node: nodes.ClassDef) -> list[str]:
        """Extract base classes and other dependencies of a class."""
        deps: list[str] = []
        for base in node.bases:
            if isinstance(base, nodes.Name):
                deps.append(base.name)
            elif isinstance(base, nodes.Attribute):
                deps.append(base.attrname)
        return deps
