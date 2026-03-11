"""Python source code parser using astroid."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import astroid
from astroid import nodes

from cia.parser.base import (
    BaseParser,
    Class,
    Dependency,
    Function,
    Import,
    ParsedModule,
    Symbol,
    Variable,
)


class PythonParser(BaseParser):
    """Parser for Python source files using astroid.

    Parsed results are cached per *resolved* file path so that repeated calls
    to :meth:`parse_file` for the same path return the cached
    :class:`ParsedModule` without re-reading the file.
    """

    def __init__(self) -> None:
        self._cache: dict[Path, ParsedModule] = {}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop all cached parse results."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Return the number of cached modules."""
        return len(self._cache)

    # ------------------------------------------------------------------
    # BaseParser interface
    # ------------------------------------------------------------------

    def get_supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser supports."""
        return [".py"]

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a single Python file and return a *ParsedModule*.

        Results are cached by resolved path.
        """
        resolved = file_path.resolve()
        if resolved in self._cache:
            return self._cache[resolved]

        module_name = file_path.stem
        parsed = ParsedModule(file_path=file_path, module_name=module_name)

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = astroid.parse(source, module_name=module_name)
        except astroid.exceptions.AstroidSyntaxError as exc:
            parsed.errors.append(f"Syntax error: {exc}")
            self._cache[resolved] = parsed
            return parsed
        except Exception as exc:  # noqa: BLE001
            parsed.errors.append(f"Parse error: {exc}")
            self._cache[resolved] = parsed
            return parsed

        parsed.ast = tree
        parsed.imports = self._extract_imports(tree)
        parsed.functions = self._extract_functions(tree, file_path)
        parsed.classes = self._extract_classes(tree, file_path)
        parsed.variables = self._extract_variables(tree, file_path)
        parsed.dependencies = self._extract_dependencies(tree, parsed)
        parsed.symbols = self._build_symbols(parsed)

        self._cache[resolved] = parsed
        return parsed

    def get_imports(self, parsed: ParsedModule) -> list[Import]:
        """Return imports already extracted during parsing."""
        return parsed.imports

    def get_functions(self, parsed: ParsedModule) -> list[Function]:
        """Return functions already extracted during parsing."""
        return parsed.functions

    def get_classes(self, parsed: ParsedModule) -> list[Class]:
        """Return classes already extracted during parsing."""
        return parsed.classes

    def get_dependencies(self, parsed: ParsedModule) -> list[Dependency]:
        """Return dependencies already extracted during parsing."""
        return parsed.dependencies

    def parse_directory(self, directory: Path) -> list[ParsedModule]:
        """Parse all Python files in a directory recursively."""
        results: list[ParsedModule] = []
        for ext in self.get_supported_extensions():
            for file_path in sorted(directory.rglob(f"*{ext}")):
                results.append(self.parse_file(file_path))
        return results

    # ------------------------------------------------------------------
    # Import extraction
    # ------------------------------------------------------------------

    def _extract_imports(self, tree: nodes.Module) -> list[Import]:
        """Extract all import statements from the AST."""
        imports: list[Import] = []
        for node in tree.body:
            if isinstance(node, nodes.Import):
                for name, alias in node.names:
                    imports.append(
                        Import(
                            module=name,
                            names=[],
                            alias=alias,
                            is_relative=False,
                            level=0,
                            line_number=node.lineno,
                        )
                    )
            elif isinstance(node, nodes.ImportFrom):
                module = node.modname or ""
                level = node.level or 0
                names = [n for n, _ in (node.names or [])]
                aliases = {n: a for n, a in (node.names or []) if a}
                imports.append(
                    Import(
                        module=module,
                        names=names,
                        alias=aliases.get(names[0]) if len(names) == 1 else None,
                        is_relative=level > 0,
                        level=level,
                        line_number=node.lineno,
                    )
                )
        return imports

    # ------------------------------------------------------------------
    # Function extraction
    # ------------------------------------------------------------------

    def _extract_functions(
        self, tree: nodes.Module, file_path: Path
    ) -> list[Function]:
        """Extract top-level function definitions."""
        functions: list[Function] = []
        for node in tree.body:
            if isinstance(node, nodes.FunctionDef):
                functions.append(self._make_function(node, tree.name, file_path))
        return functions

    def _make_function(
        self,
        node: nodes.FunctionDef,
        qualifier: str,
        file_path: Path,
        is_method: bool = False,
    ) -> Function:
        """Build a :class:`Function` from an astroid *FunctionDef*."""
        return Function(
            name=node.name,
            qualified_name=f"{qualifier}.{node.name}",
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            decorators=self._get_decorator_names(node),
            args=self._get_arg_names(node),
            dependencies=self._get_function_call_deps(node),
            is_method=is_method,
        )

    # ------------------------------------------------------------------
    # Class extraction
    # ------------------------------------------------------------------

    def _extract_classes(self, tree: nodes.Module, file_path: Path) -> list[Class]:
        """Extract class definitions with their methods."""
        classes: list[Class] = []
        for node in tree.body:
            if isinstance(node, nodes.ClassDef):
                methods = [
                    self._make_function(
                        m, f"{tree.name}.{node.name}", file_path, is_method=True
                    )
                    for m in node.mymethods()
                ]
                classes.append(
                    Class(
                        name=node.name,
                        qualified_name=f"{tree.name}.{node.name}",
                        file_path=file_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        bases=self._get_base_names(node),
                        methods=methods,
                        decorators=self._get_decorator_names(node),
                        dependencies=self._get_base_names(node),
                    )
                )
        return classes

    # ------------------------------------------------------------------
    # Variable extraction
    # ------------------------------------------------------------------

    def _extract_variables(
        self, tree: nodes.Module, file_path: Path
    ) -> list[Variable]:
        """Extract module-level variable assignments."""
        variables: list[Variable] = []
        for node in tree.body:
            if isinstance(node, nodes.Assign):
                for target in node.targets:
                    if isinstance(target, nodes.AssignName):
                        value_type = type(node.value).__name__ if node.value else None
                        variables.append(
                            Variable(
                                name=target.name,
                                file_path=file_path,
                                line_number=node.lineno,
                                value_type=value_type,
                            )
                        )
            elif isinstance(node, nodes.AnnAssign) and node.target:
                if isinstance(node.target, nodes.AssignName):
                    variables.append(
                        Variable(
                            name=node.target.name,
                            file_path=file_path,
                            line_number=node.lineno,
                            value_type="annotated",
                        )
                    )
        return variables

    # ------------------------------------------------------------------
    # Dependency extraction
    # ------------------------------------------------------------------

    def _extract_dependencies(
        self, tree: nodes.Module, parsed: ParsedModule
    ) -> list[Dependency]:
        """Derive dependency relationships from the parsed data."""
        deps: list[Dependency] = []
        module_qn = tree.name

        for imp in parsed.imports:
            deps.append(
                Dependency(
                    source=module_qn,
                    target=imp.module if imp.module else f"relative_level_{imp.level}",
                    dependency_type="import",
                )
            )

        for func in parsed.functions:
            for call in func.dependencies:
                deps.append(
                    Dependency(
                        source=func.qualified_name,
                        target=call,
                        dependency_type="call",
                    )
                )

        for cls in parsed.classes:
            for base in cls.bases:
                deps.append(
                    Dependency(
                        source=cls.qualified_name,
                        target=base,
                        dependency_type="inherit",
                    )
                )
            for method in cls.methods:
                for call in method.dependencies:
                    deps.append(
                        Dependency(
                            source=method.qualified_name,
                            target=call,
                            dependency_type="call",
                        )
                    )

        return deps

    # ------------------------------------------------------------------
    # Symbol list (backwards-compatible flat list)
    # ------------------------------------------------------------------

    def _build_symbols(self, parsed: ParsedModule) -> list[Symbol]:
        """Build the flat *symbols* list from functions, classes, variables."""
        symbols: list[Symbol] = []

        for func in parsed.functions:
            symbols.append(
                Symbol(
                    name=func.name,
                    qualified_name=func.qualified_name,
                    symbol_type="function",
                    file_path=func.file_path,
                    line_start=func.line_start,
                    line_end=func.line_end,
                    dependencies=func.dependencies,
                    decorators=func.decorators,
                )
            )

        for cls in parsed.classes:
            symbols.append(
                Symbol(
                    name=cls.name,
                    qualified_name=cls.qualified_name,
                    symbol_type="class",
                    file_path=cls.file_path,
                    line_start=cls.line_start,
                    line_end=cls.line_end,
                    dependencies=cls.dependencies,
                    decorators=cls.decorators,
                )
            )
            for method in cls.methods:
                symbols.append(
                    Symbol(
                        name=method.name,
                        qualified_name=method.qualified_name,
                        symbol_type="method",
                        file_path=method.file_path,
                        line_start=method.line_start,
                        line_end=method.line_end,
                        dependencies=method.dependencies,
                        decorators=method.decorators,
                    )
                )

        for var in parsed.variables:
            symbols.append(
                Symbol(
                    name=var.name,
                    qualified_name=f"{parsed.module_name}.{var.name}",
                    symbol_type="variable",
                    file_path=var.file_path,
                    line_start=var.line_number,
                    line_end=var.line_number,
                )
            )

        return symbols

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_decorator_names(
        node: nodes.FunctionDef | nodes.ClassDef,
    ) -> list[str]:
        """Return the names of all decorators on *node*."""
        if node.decorators is None:
            return []
        names: list[str] = []
        for dec in node.decorators.nodes:
            if isinstance(dec, nodes.Name):
                names.append(dec.name)
            elif isinstance(dec, nodes.Attribute):
                names.append(dec.as_string())
            elif isinstance(dec, nodes.Call):
                if isinstance(dec.func, nodes.Name):
                    names.append(dec.func.name)
                elif isinstance(dec.func, nodes.Attribute):
                    names.append(dec.func.as_string())
        return names

    @staticmethod
    def _get_arg_names(node: nodes.FunctionDef) -> list[str]:
        """Return positional argument names of *node*."""
        if node.args is None:
            return []
        return [a.name for a in node.args.args or []]

    @staticmethod
    def _get_function_call_deps(node: nodes.FunctionDef) -> list[str]:
        """Extract names called within a function body."""
        deps: list[str] = []
        for call_node in node.nodes_of_class(nodes.Call):
            if isinstance(call_node.func, nodes.Name):
                deps.append(call_node.func.name)
            elif isinstance(call_node.func, nodes.Attribute):
                deps.append(call_node.func.attrname)
        return sorted(set(deps))

    @staticmethod
    def _get_base_names(node: nodes.ClassDef) -> list[str]:
        """Extract base class names from a *ClassDef*."""
        bases: list[str] = []
        for base in node.bases:
            if isinstance(base, nodes.Name):
                bases.append(base.name)
            elif isinstance(base, nodes.Attribute):
                bases.append(base.as_string())
        return bases
