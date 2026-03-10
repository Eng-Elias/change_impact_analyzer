# API Reference

## `cia.parser`

### `BaseParser`

Abstract base class for language-specific parsers.

- `parse_file(file_path: Path) -> ParsedModule` — Parse a single source file.
- `parse_directory(directory: Path) -> list[ParsedModule]` — Parse all files in a directory.
- `get_supported_extensions() -> list[str]` — Return supported file extensions.

### `PythonParser(BaseParser)`

Parser for Python source files using `astroid`.

---

## `cia.graph`

### `DependencyGraph`

Module-level import dependency graph.

- `build_from_modules(modules: list[ParsedModule])` — Build the graph.
- `get_dependents(module_name: str) -> set[str]` — Direct reverse dependencies.
- `get_dependencies(module_name: str) -> set[str]` — Direct dependencies.
- `get_transitive_dependents(module_name: str) -> set[str]` — All transitive dependents.

### `CallGraph`

Function/method-level call graph.

- `build_from_modules(modules: list[ParsedModule])` — Build the graph.
- `get_callers(qualified_name: str) -> set[str]` — Direct callers.
- `get_callees(qualified_name: str) -> set[str]` — Direct callees.
- `get_transitive_callers(qualified_name: str) -> set[str]` — All transitive callers.

---

## `cia.analyzer`

### `ChangeDetector`

- `detect_changes(diff_text: str) -> list[Change]` — Parse unified diff.
- `map_changes_to_symbols(changes, symbols) -> list[Change]` — Map changes to symbols.

### `ImpactAnalyzer`

- `__init__(dependency_graph, call_graph)` — Initialize with graphs.
- `analyze(changes: list[Change]) -> AnalysisReport` — Run impact analysis.

---

## `cia.risk`

### `RiskScorer`

- `score_report(report: AnalysisReport) -> list[RiskAssessment]` — Score all impacts.

### `RiskFactors`

- `set_value(name: str, value: float)` — Set a risk factor value.
- `total_score() -> float` — Calculate total weighted score.

---

## `cia.git`

### `GitIntegration`

- `get_staged_diff() -> str` — Staged changes diff.
- `get_unstaged_diff() -> str` — Unstaged changes diff.
- `get_changed_files(staged: bool) -> list[Path]` — Changed file paths.

### `HookManager`

- `install() -> Path` — Install the pre-commit hook.
- `uninstall() -> bool` — Remove the pre-commit hook.

---

## `cia.report`

### `JsonReporter` / `MarkdownReporter` / `HtmlReporter`

- `generate(report, risk_assessments?) -> str` — Generate report string.
- `write(report, output_path, risk_assessments?) -> Path` — Write report to file.
