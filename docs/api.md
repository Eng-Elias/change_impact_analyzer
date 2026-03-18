# API Reference

> Generated from source docstrings. For the latest details, inspect the source
> in `src/cia/` or run `python -c "import cia.<module>; help(cia.<module>)"`.

---

## `cia` — Package Root

```python
from cia import __version__
```

| Symbol | Type | Description |
|--------|------|-------------|
| `__version__` | `str` | Semantic version string (e.g. `"0.1.0"`). |

---

## `cia.parser` — Source Code Parsing

### Data Structures

```python
from cia.parser.base import (
    SymbolType, Import, Function, Class, Variable, Symbol, ParsedModule,
)
```

| Class | Description |
|-------|-------------|
| `SymbolType` | Enum — `FUNCTION`, `CLASS`, `METHOD`, `VARIABLE`, `MODULE`. |
| `Import` | Dataclass — represents a single import statement (`module`, `name`, `alias`). |
| `Function` | Dataclass — function/method with `name`, `args`, `decorators`, `lineno`, `end_lineno`. |
| `Class` | Dataclass — class with `name`, `bases`, `methods`, `lineno`, `end_lineno`. |
| `Variable` | Dataclass — module-level variable assignment. |
| `Symbol` | Dataclass — unified wrapper (`name`, `symbol_type`, `lineno`, `end_lineno`). |
| `ParsedModule` | Dataclass — full parse result (`file_path`, `module_name`, `imports`, `functions`, `classes`, `variables`, `symbols`). |

### `BaseParser`

Abstract base class for language-specific parsers.

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse_file` | `(file_path: Path) -> ParsedModule` | Parse a single source file. |
| `parse_directory` | `(directory: Path) -> list[ParsedModule]` | Parse all source files in a directory tree. |
| `get_supported_extensions` | `() -> list[str]` | Return list of file extensions this parser handles. |

### `PythonParser(BaseParser)`

Concrete parser for Python files using `astroid`.

```python
from cia.parser.python_parser import PythonParser

parser = PythonParser()
module = parser.parse_file(Path("src/cia/cli.py"))
print(module.functions)   # list of Function objects
print(module.classes)     # list of Class objects
print(module.imports)     # list of Import objects
```

---

## `cia.graph` — Dependency & Call Graphs

### `DependencyGraph`

Module-level import dependency graph backed by NetworkX.

```python
from cia.graph.dependency_graph import DependencyGraph

dg = DependencyGraph()
dg.build_from_modules(parsed_modules)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `build_from_modules` | `(modules: list[ParsedModule]) -> None` | Build the graph from parsed modules. |
| `add_module` | `(module_name: str) -> None` | Add a single module node. |
| `add_dependency` | `(from_mod: str, to_mod: str) -> None` | Add a directed edge. |
| `get_dependencies` | `(module_name: str) -> set[str]` | Direct imports of a module. |
| `get_dependents` | `(module_name: str) -> set[str]` | Modules that import this one. |
| `get_transitive_dependencies` | `(module_name: str) -> set[str]` | All transitive imports. |
| `get_transitive_dependents` | `(module_name: str) -> set[str]` | All transitive reverse dependencies. |

### `CallGraph`

Function/method-level call graph backed by NetworkX.

```python
from cia.graph.call_graph import CallGraph

cg = CallGraph()
cg.build_from_modules(parsed_modules)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `build_from_modules` | `(modules: list[ParsedModule]) -> None` | Build from parsed modules. |
| `add_function` | `(qualified_name: str) -> None` | Add a function node. |
| `add_call` | `(caller: str, callee: str) -> None` | Add a directed call edge. |
| `get_callers` | `(qualified_name: str) -> set[str]` | Direct callers. |
| `get_callees` | `(qualified_name: str) -> set[str]` | Direct callees. |
| `get_transitive_callers` | `(qualified_name: str) -> set[str]` | All transitive callers. |
| `get_transitive_callees` | `(qualified_name: str) -> set[str]` | All transitive callees. |

---

## `cia.analyzer` — Change Detection & Impact Analysis

### `Change` / `ChangeSet`

```python
from cia.analyzer.change_detector import Change, ChangeSet
```

| Class | Key Fields | Description |
|-------|-----------|-------------|
| `Change` | `file_path`, `old_lines`, `new_lines`, `symbols` | A single file change from a Git diff. |
| `ChangeSet` | `changes: list[Change]` | Collection of changes from a diff. |

### `ChangeDetector`

```python
from cia.analyzer.change_detector import ChangeDetector

detector = ChangeDetector()
changeset = detector.detect_changes(git_integration, staged=True)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `detect_changes` | `(git: GitIntegration, staged: bool = True) -> ChangeSet` | Detect changes from staged or unstaged diff. |
| `detect_changes_for_range` | `(git: GitIntegration, commit_range: str) -> ChangeSet` | Detect changes in a commit range. |
| `parse_diff` | `(diff_text: str) -> list[Change]` | Parse unified diff text. |
| `map_changes_to_symbols` | `(changes, parsed_modules) -> list[Change]` | Map line ranges to symbols. |
| `map_changes_to_entities` | `(changes, parsed_modules) -> list[Change]` | Map changes to high-level entities. |

### `ImpactAnalyzer`

```python
from cia.analyzer.impact_analyzer import ImpactAnalyzer, ImpactReport

analyzer = ImpactAnalyzer(dependency_graph)
report = analyzer.analyze_change_set(changeset, risk_score=risk)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `analyze_change_set` | `(changeset: ChangeSet, risk_score: RiskScore \| None = None) -> ImpactReport` | Full orchestrated analysis. |

### `ImpactReport`

| Field | Type | Description |
|-------|------|-------------|
| `analysis` | `AnalysisReport` | Core analysis results. |
| `risk` | `RiskScore \| None` | Risk assessment. |
| `affected_tests` | `list[Path]` | Predicted affected test files. |
| `recommendations` | `list[str]` | Actionable suggestions. |
| `affected_modules` | `list[str]` | Affected module names. |

### `TestAnalyzer`

```python
from cia.analyzer.test_analyzer import TestAnalyzer

ta = TestAnalyzer()
mapping = ta.build_test_mapping(repo_path)
affected = ta.predict_affected_tests(changed_modules, mapping)
suggestions = ta.suggest_missing_tests(changed_modules, test_mapping=mapping)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `build_test_mapping` | `(repo_path: Path) -> dict` | Map test files to source modules. |
| `predict_affected_tests` | `(changed_modules, mapping) -> list[Path]` | Predict which tests are affected. |
| `suggest_missing_tests` | `(changed_modules, test_mapping) -> list[TestSuggestion]` | Suggest tests for uncovered modules. |
| `generate_pytest_expression` | `(test_files) -> str` | Generate a `-k` expression. |
| `generate_pytest_args` | `(test_files) -> list[str]` | Generate CLI args for pytest. |

---

## `cia.risk` — Risk Scoring

### `RiskScorer`

```python
from cia.risk.risk_scorer import RiskScorer

scorer = RiskScorer()
risk = scorer.calculate_risk(changeset)
print(risk.overall_score)   # 0–100
print(risk.level)           # RiskLevel enum
print(risk.explanations)    # human-readable list
print(risk.suggestions)     # actionable suggestions
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `calculate_risk` | `(changeset: ChangeSet, **context) -> RiskScore` | Compute composite risk score. |

### `RiskScore`

| Field | Type | Description |
|-------|------|-------------|
| `overall_score` | `float` | Composite score (0–100). |
| `level` | `RiskLevel` | `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. |
| `factor_scores` | `dict[str, float]` | Per-factor scores. |
| `explanations` | `list[str]` | Natural-language breakdown. |
| `suggestions` | `list[str]` | Actionable improvement hints. |

### `RiskLevel`

Enum: `LOW` (0–25), `MEDIUM` (26–50), `HIGH` (51–75), `CRITICAL` (76–100).

---

## `cia.git` — Git Integration

### `GitIntegration`

```python
from cia.git.git_integration import GitIntegration

git = GitIntegration(Path("."))
assert git.is_git_repository()
diff = git.get_staged_diff()
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_git_repository` | `() -> bool` | Check if path is a Git repo. |
| `get_staged_diff` | `() -> str` | Unified diff of staged changes. |
| `get_unstaged_diff` | `() -> str` | Unified diff of unstaged changes. |
| `get_diff_for_range` | `(commit_range: str) -> str` | Diff between two commits. |
| `get_changed_files` | `(staged: bool = True) -> list[Path]` | List of changed file paths. |

### `HookManager`

```python
from cia.git.hooks import HookManager

manager = HookManager(Path("."))
hook_path = manager.install(block_threshold="high")
manager.uninstall()
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `install` | `(block_threshold: str = "none") -> Path` | Install the pre-commit hook script. |
| `uninstall` | `() -> bool` | Remove the CIA hook. Returns `True` if removed. |

---

## `cia.report` — Report Generation

All reporters accept an `ImpactReport` and return a formatted string.

```python
from cia.report import JsonReporter, MarkdownReporter, HtmlReporter

json_str = JsonReporter().generate(impact_report)
md_str   = MarkdownReporter().generate(impact_report)
html_str = HtmlReporter().generate(impact_report)
```

### `JsonReporter`

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `(report: ImpactReport) -> str` | JSON with stable `schema_version`. |
| `write` | `(report: ImpactReport, path: Path) -> Path` | Write JSON to file. |

### `MarkdownReporter`

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `(report: ImpactReport) -> str` | GitHub-flavoured Markdown. |
| `write` | `(report: ImpactReport, path: Path) -> Path` | Write Markdown to file. |

### `HtmlReporter`

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `(report: ImpactReport) -> str` | Self-contained HTML with D3.js graph. |
| `write` | `(report: ImpactReport, path: Path) -> Path` | Write HTML to file. |

---

## `cia.config` — Configuration Management

```python
from cia.config import load_config, get_config_value, set_config_value, find_config_file

cfg = load_config(Path("."))                       # full resolution
val = get_config_value(cfg, "analysis.format")     # dot-separated key
set_config_value(Path(".ciarc"), "threshold", "80") # persist to file
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `find_config_file` | `(start: Path) -> Path \| None` | Walk up to find `.ciarc*`. |
| `load_config` | `(start: Path) -> dict` | Load defaults + file + env vars. |
| `get_config_value` | `(cfg: dict, key: str) -> Any` | Lookup by full or short key. |
| `set_config_value` | `(path: Path, key: str, value: str) -> None` | Write to TOML/JSON file. |
| `load_env_overrides` | `() -> dict` | Parse `CIA_*` env vars. |

---

## `cia.cli` — Command-Line Interface

Entry point: `cia = cia.cli:main`

| Command | Description |
|---------|-------------|
| `cia analyze [PATH]` | Analyse staged/unstaged/commit-range changes. |
| `cia test [PATH]` | Predict affected tests and suggest missing coverage. |
| `cia install-hook [PATH]` | Install pre-commit hook. |
| `cia uninstall-hook [PATH]` | Remove pre-commit hook. |
| `cia config [PATH]` | Show or modify configuration. |
| `cia init [PATH]` | Create a `.ciarc` file. |
| `cia version` | Show detailed version info. |
| `cia graph [PATH]` | Build dependency graph (stub). |

Exit codes: `0` = success, `1` = high risk, `2` = error.
