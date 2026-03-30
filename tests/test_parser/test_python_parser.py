"""Comprehensive tests for PythonParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.parser.python_parser import PythonParser


@pytest.fixture
def parser() -> PythonParser:
    return PythonParser()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write *content* to ``tmp_path / name`` and return the path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ==================================================================
# Parsing simple Python files
# ==================================================================


class TestParseSimpleFiles:
    """Test parsing simple Python files."""

    def test_parse_empty_file(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "empty.py", "")
        result = parser.parse_file(f)
        assert result.module_name == "empty"
        assert result.errors == []
        assert result.imports == []
        assert result.functions == []
        assert result.classes == []
        assert result.variables == []

    def test_parse_simple_function(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(
            tmp_path, "simple.py", "def greet(name):\n    return f'Hello {name}'\n"
        )
        result = parser.parse_file(f)
        assert len(result.functions) == 1
        assert result.functions[0].name == "greet"
        assert result.functions[0].qualified_name == "simple.greet"
        assert "name" in result.functions[0].args

    def test_parse_file_preserves_file_path(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        f = _write(tmp_path, "mod.py", "x = 1\n")
        result = parser.parse_file(f)
        assert result.file_path == f

    def test_parse_file_stores_ast(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "mod.py", "x = 1\n")
        result = parser.parse_file(f)
        assert result.ast is not None

    def test_parse_module_name_from_stem(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        f = _write(tmp_path, "my_module.py", "pass\n")
        result = parser.parse_file(f)
        assert result.module_name == "my_module"


# ==================================================================
# Import extraction
# ==================================================================


class TestImports:
    """Test extraction of import statements."""

    def test_import_statement(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "imp.py", "import os\nimport sys\n")
        result = parser.parse_file(f)
        assert len(result.imports) == 2
        assert result.imports[0].module == "os"
        assert result.imports[1].module == "sys"
        assert result.imports[0].is_relative is False

    def test_from_import(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "imp.py", "from os.path import join, exists\n")
        result = parser.parse_file(f)
        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "os.path"
        assert "join" in imp.names
        assert "exists" in imp.names
        assert imp.is_relative is False

    def test_relative_import(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(
            tmp_path, "rel.py", "from . import sibling\nfrom ..pkg import thing\n"
        )
        result = parser.parse_file(f)
        assert len(result.imports) == 2
        assert result.imports[0].is_relative is True
        assert result.imports[0].level == 1
        assert result.imports[1].is_relative is True
        assert result.imports[1].level == 2
        assert result.imports[1].module == "pkg"

    def test_import_alias(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "alias.py", "import numpy as np\n")
        result = parser.parse_file(f)
        assert result.imports[0].module == "numpy"
        assert result.imports[0].alias == "np"

    def test_from_import_alias(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "alias.py", "from pathlib import Path as P\n")
        result = parser.parse_file(f)
        imp = result.imports[0]
        assert imp.module == "pathlib"
        assert "Path" in imp.names
        assert imp.alias == "P"

    def test_import_line_numbers(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "lines.py", "import os\n\nimport sys\n")
        result = parser.parse_file(f)
        assert result.imports[0].line_number == 1
        assert result.imports[1].line_number == 3

    def test_get_imports_accessor(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "acc.py", "import os\n")
        result = parser.parse_file(f)
        assert parser.get_imports(result) is result.imports


# ==================================================================
# Function extraction
# ==================================================================


class TestFunctions:
    """Test extraction of function definitions."""

    def test_simple_function(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "funcs.py", "def add(a, b):\n    return a + b\n")
        result = parser.parse_file(f)
        assert len(result.functions) == 1
        fn = result.functions[0]
        assert fn.name == "add"
        assert fn.qualified_name == "funcs.add"
        assert set(fn.args) == {"a", "b"}
        assert fn.is_method is False

    def test_function_line_numbers(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "def first():\n    pass\n\ndef second():\n    pass\n"
        f = _write(tmp_path, "funcs.py", src)
        result = parser.parse_file(f)
        assert result.functions[0].line_start == 1
        assert result.functions[1].line_start == 4

    def test_function_with_decorator(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        src = "@staticmethod\ndef util():\n    pass\n"
        f = _write(tmp_path, "dec.py", src)
        result = parser.parse_file(f)
        fn = result.functions[0]
        assert "staticmethod" in fn.decorators

    def test_function_with_parameterized_decorator(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        src = "@app.route('/home')\ndef index():\n    pass\n"
        f = _write(tmp_path, "dec2.py", src)
        result = parser.parse_file(f)
        fn = result.functions[0]
        assert len(fn.decorators) == 1
        assert "app.route" in fn.decorators[0]

    def test_function_dependencies(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "def foo():\n    bar()\n    obj.baz()\n"
        f = _write(tmp_path, "deps.py", src)
        result = parser.parse_file(f)
        fn = result.functions[0]
        assert "bar" in fn.dependencies
        assert "baz" in fn.dependencies

    def test_multiple_functions(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "def a():\n    pass\ndef b():\n    pass\ndef c():\n    pass\n"
        f = _write(tmp_path, "multi.py", src)
        result = parser.parse_file(f)
        assert [fn.name for fn in result.functions] == ["a", "b", "c"]

    def test_get_functions_accessor(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "acc.py", "def f(): pass\n")
        result = parser.parse_file(f)
        assert parser.get_functions(result) is result.functions


# ==================================================================
# Class extraction
# ==================================================================


class TestClasses:
    """Test extraction of class definitions."""

    def test_simple_class(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "class Foo:\n    pass\n"
        f = _write(tmp_path, "cls.py", src)
        result = parser.parse_file(f)
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Foo"
        assert cls.qualified_name == "cls.Foo"

    def test_class_with_base(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "class Child(Parent):\n    pass\n"
        f = _write(tmp_path, "inherit.py", src)
        result = parser.parse_file(f)
        cls = result.classes[0]
        assert "Parent" in cls.bases

    def test_class_with_methods(self, parser: PythonParser, tmp_path: Path) -> None:
        src = (
            "class MyClass:\n"
            "    def __init__(self):\n"
            "        pass\n"
            "    def do_work(self):\n"
            "        pass\n"
        )
        f = _write(tmp_path, "methods.py", src)
        result = parser.parse_file(f)
        cls = result.classes[0]
        method_names = [m.name for m in cls.methods]
        assert "__init__" in method_names
        assert "do_work" in method_names
        for m in cls.methods:
            assert m.is_method is True

    def test_class_with_decorator(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "@dataclass\nclass Config:\n    x: int = 0\n"
        f = _write(tmp_path, "deco_cls.py", src)
        result = parser.parse_file(f)
        cls = result.classes[0]
        assert "dataclass" in cls.decorators

    def test_class_dependencies_include_bases(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        src = "class A(B, C):\n    pass\n"
        f = _write(tmp_path, "multi_base.py", src)
        result = parser.parse_file(f)
        cls = result.classes[0]
        assert set(cls.bases) == {"B", "C"}
        assert set(cls.dependencies) == {"B", "C"}

    def test_method_dependencies(self, parser: PythonParser, tmp_path: Path) -> None:
        src = (
            "class Svc:\n"
            "    def run(self):\n"
            "        self.helper()\n"
            "        external()\n"
        )
        f = _write(tmp_path, "svc.py", src)
        result = parser.parse_file(f)
        method = result.classes[0].methods[0]
        assert "helper" in method.dependencies
        assert "external" in method.dependencies

    def test_get_classes_accessor(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "acc.py", "class X: pass\n")
        result = parser.parse_file(f)
        assert parser.get_classes(result) is result.classes

    def test_multiple_classes(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "class A:\n    pass\nclass B:\n    pass\n"
        f = _write(tmp_path, "multi.py", src)
        result = parser.parse_file(f)
        assert len(result.classes) == 2
        assert [c.name for c in result.classes] == ["A", "B"]


# ==================================================================
# Variable extraction
# ==================================================================


class TestVariables:
    """Test extraction of module-level variable assignments."""

    def test_simple_assignment(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "var.py", "x = 42\n")
        result = parser.parse_file(f)
        assert len(result.variables) == 1
        assert result.variables[0].name == "x"
        assert result.variables[0].line_number == 1

    def test_multiple_assignments(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "var.py", "a = 1\nb = 'hello'\nc = [1, 2]\n")
        result = parser.parse_file(f)
        names = [v.name for v in result.variables]
        assert names == ["a", "b", "c"]

    def test_annotated_assignment(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "ann.py", "x: int = 10\n")
        result = parser.parse_file(f)
        assert len(result.variables) == 1
        assert result.variables[0].name == "x"
        assert result.variables[0].value_type == "annotated"

    def test_variables_appear_in_symbols(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        f = _write(tmp_path, "var.py", "DEBUG = True\n")
        result = parser.parse_file(f)
        var_symbols = [s for s in result.symbols if s.symbol_type == "variable"]
        assert len(var_symbols) == 1
        assert var_symbols[0].name == "DEBUG"


# ==================================================================
# Dependencies
# ==================================================================


class TestDependencies:
    """Test dependency extraction."""

    def test_import_dependencies(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "dep.py", "import os\nfrom sys import argv\n")
        result = parser.parse_file(f)
        dep_types = {d.dependency_type for d in result.dependencies}
        assert "import" in dep_types
        targets = [
            d.target for d in result.dependencies if d.dependency_type == "import"
        ]
        assert "os" in targets
        assert "sys" in targets

    def test_call_dependencies(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "call.py", "def foo():\n    bar()\n")
        result = parser.parse_file(f)
        call_deps = [d for d in result.dependencies if d.dependency_type == "call"]
        assert any(d.target == "bar" for d in call_deps)

    def test_inherit_dependencies(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "inh.py", "class Child(Base):\n    pass\n")
        result = parser.parse_file(f)
        inh_deps = [d for d in result.dependencies if d.dependency_type == "inherit"]
        assert any(d.target == "Base" for d in inh_deps)

    def test_get_dependencies_accessor(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        f = _write(tmp_path, "acc.py", "import os\n")
        result = parser.parse_file(f)
        assert parser.get_dependencies(result) is result.dependencies


# ==================================================================
# Symbols (flat list)
# ==================================================================


class TestSymbols:
    """Test the flat symbols list."""

    def test_symbols_include_all_types(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        src = (
            "VAR = 1\n"
            "def func(): pass\n"
            "class Cls:\n"
            "    def method(self): pass\n"
        )
        f = _write(tmp_path, "all.py", src)
        result = parser.parse_file(f)
        types = {s.symbol_type for s in result.symbols}
        assert types == {"variable", "function", "class", "method"}

    def test_symbol_decorators(self, parser: PythonParser, tmp_path: Path) -> None:
        src = "@staticmethod\ndef util():\n    pass\n"
        f = _write(tmp_path, "sdec.py", src)
        result = parser.parse_file(f)
        fn_sym = [s for s in result.symbols if s.symbol_type == "function"][0]
        assert "staticmethod" in fn_sym.decorators


# ==================================================================
# Syntax error handling
# ==================================================================


class TestErrorHandling:
    """Test graceful handling of parse errors."""

    def test_syntax_error_returns_parsed_module_with_error(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        f = _write(tmp_path, "bad.py", "def oops(\n")
        result = parser.parse_file(f)
        assert len(result.errors) == 1
        assert "yntax" in result.errors[0]  # "Syntax error" or "syntax error"
        assert result.functions == []
        assert result.classes == []

    def test_nonexistent_file(self, parser: PythonParser, tmp_path: Path) -> None:
        f = tmp_path / "missing.py"
        result = parser.parse_file(f)
        assert len(result.errors) == 1

    def test_binary_file(self, parser: PythonParser, tmp_path: Path) -> None:
        f = tmp_path / "bin.py"
        f.write_bytes(b"\x00\x01\x02\x80\x81")
        result = parser.parse_file(f)
        assert len(result.errors) >= 1


# ==================================================================
# Caching
# ==================================================================


class TestCaching:
    """Test the parse result caching mechanism."""

    def test_cache_returns_same_object(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        f = _write(tmp_path, "cached.py", "x = 1\n")
        first = parser.parse_file(f)
        second = parser.parse_file(f)
        assert first is second

    def test_cache_size_increments(self, parser: PythonParser, tmp_path: Path) -> None:
        assert parser.cache_size == 0
        _write(tmp_path, "a.py", "pass\n")
        _write(tmp_path, "b.py", "pass\n")
        parser.parse_file(tmp_path / "a.py")
        assert parser.cache_size == 1
        parser.parse_file(tmp_path / "b.py")
        assert parser.cache_size == 2

    def test_clear_cache(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "c.py", "pass\n")
        parser.parse_file(f)
        assert parser.cache_size == 1
        parser.clear_cache()
        assert parser.cache_size == 0

    def test_cache_persists_errors(self, parser: PythonParser, tmp_path: Path) -> None:
        f = _write(tmp_path, "err.py", "def oops(\n")
        first = parser.parse_file(f)
        second = parser.parse_file(f)
        assert first is second
        assert len(first.errors) == 1


# ==================================================================
# Directory parsing
# ==================================================================


class TestParseDirectory:
    """Test parsing entire directories."""

    def test_parse_directory(self, parser: PythonParser, tmp_path: Path) -> None:
        _write(tmp_path, "a.py", "def a(): pass\n")
        _write(tmp_path, "b.py", "class B: pass\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        _write(sub, "c.py", "x = 1\n")
        results = parser.parse_directory(tmp_path)
        names = {r.module_name for r in results}
        assert names == {"a", "b", "c"}

    def test_parse_directory_skips_non_python(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        _write(tmp_path, "mod.py", "pass\n")
        (tmp_path / "data.txt").write_text("not python", encoding="utf-8")
        results = parser.parse_directory(tmp_path)
        assert len(results) == 1

    def test_supported_extensions(self, parser: PythonParser) -> None:
        assert parser.get_supported_extensions() == [".py"]


# ==================================================================
# Complex / integration scenarios
# ==================================================================


class TestComplexScenarios:
    """Integration-style tests with realistic code snippets."""

    def test_full_module(self, parser: PythonParser, tmp_path: Path) -> None:
        src = (
            '"""Module docstring."""\n'
            "\n"
            "import os\n"
            "from pathlib import Path\n"
            "from . import utils\n"
            "\n"
            "TIMEOUT = 30\n"
            "\n"
            "\n"
            "def connect(host, port):\n"
            "    return os.path.join(host, str(port))\n"
            "\n"
            "\n"
            "class Client:\n"
            '    """A client."""\n'
            "\n"
            "    def __init__(self, url):\n"
            "        self.url = url\n"
            "\n"
            "    def fetch(self):\n"
            "        return connect(self.url, 80)\n"
            "\n"
        )
        f = _write(tmp_path, "client.py", src)
        result = parser.parse_file(f)

        assert len(result.errors) == 0
        assert len(result.imports) == 3  # os, pathlib, .utils

        rel_imports = [i for i in result.imports if i.is_relative]
        assert len(rel_imports) == 1
        assert rel_imports[0].level == 1

        assert len(result.functions) == 1
        assert result.functions[0].name == "connect"

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Client"
        assert len(cls.methods) == 2

        assert any(v.name == "TIMEOUT" for v in result.variables)

        dep_types = {d.dependency_type for d in result.dependencies}
        assert "import" in dep_types
        assert "call" in dep_types

    def test_decorated_class_and_method(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        src = (
            "from functools import lru_cache\n"
            "\n"
            "@lru_cache(maxsize=128)\n"
            "def expensive(n):\n"
            "    return n ** 2\n"
        )
        f = _write(tmp_path, "deco.py", src)
        result = parser.parse_file(f)
        fn = result.functions[0]
        assert "lru_cache" in fn.decorators
