"""Base parser interface for source code analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


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


@dataclass
class ParsedModule:
    """Result of parsing a single source file."""

    file_path: Path
    module_name: str
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseParser(ABC):
    """Abstract base class for language-specific parsers."""

    @abstractmethod
    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a single source file and extract symbols and dependencies."""
        ...

    @abstractmethod
    def parse_directory(self, directory: Path) -> list[ParsedModule]:
        """Parse all supported files in a directory recursively."""
        ...

    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser supports."""
        ...
