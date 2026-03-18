"""Base parser interface for source code analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class SymbolType(str, Enum):
    """Enumeration of recognised code symbol types."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"


@dataclass
class Import:
    """Represents a single import statement."""

    module: str
    names: list[str] = field(default_factory=list)
    alias: str | None = None
    is_relative: bool = False
    level: int = 0
    line_number: int = 0


@dataclass
class Function:
    """Represents a function or method definition."""

    name: str
    qualified_name: str
    file_path: Path
    line_start: int
    line_end: int
    decorators: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    is_method: bool = False


@dataclass
class Class:
    """Represents a class definition."""

    name: str
    qualified_name: str
    file_path: Path
    line_start: int
    line_end: int
    bases: list[str] = field(default_factory=list)
    methods: list[Function] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Variable:
    """Represents a module-level variable assignment."""

    name: str
    file_path: Path
    line_number: int
    value_type: str | None = None


@dataclass
class Dependency:
    """Represents a dependency relationship between symbols."""

    source: str
    target: str
    dependency_type: str  # "import", "call", "inherit", "reference"


@dataclass
class Symbol:
    """Represents a code symbol (function, class, method, variable)."""

    name: str
    qualified_name: str
    symbol_type: str  # "function", "class", "method", "variable"
    file_path: Path
    line_start: int
    line_end: int
    dependencies: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass
class ParsedModule:
    """Result of parsing a single source file."""

    file_path: Path
    module_name: str
    imports: list[Import] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)
    classes: list[Class] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ast: Any = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Abstract base parser
# ---------------------------------------------------------------------------


class BaseParser(ABC):
    """Abstract base class for language-specific parsers."""

    @abstractmethod
    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a single source file and return a *ParsedModule*."""
        ...

    @abstractmethod
    def get_imports(self, parsed: ParsedModule) -> list[Import]:
        """Extract import statements from a parsed module."""
        ...

    @abstractmethod
    def get_functions(self, parsed: ParsedModule) -> list[Function]:
        """Extract function definitions from a parsed module."""
        ...

    @abstractmethod
    def get_classes(self, parsed: ParsedModule) -> list[Class]:
        """Extract class definitions from a parsed module."""
        ...

    @abstractmethod
    def get_dependencies(self, parsed: ParsedModule) -> list[Dependency]:
        """Extract dependency relationships from a parsed module."""
        ...

    @abstractmethod
    def parse_directory(self, directory: Path) -> list[ParsedModule]:
        """Parse all supported files in a directory recursively."""
        ...

    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser supports."""
        ...
