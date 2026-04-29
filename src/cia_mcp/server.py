"""CIA MCP Server -- exposes CIA as MCP tools, resources, and prompts.

This is a thin adapter: CIA does the analysis, the MCP server exposes it.
All heavy lifting (parsing, graph building, risk scoring) is done by the
existing ``cia`` library.

Usage::

    # stdio (default -- works with all local AI assistants)
    cia-mcp

    # SSE (for remote / web-based clients)
    cia-mcp --transport sse --port 8080
"""

from __future__ import annotations

import contextlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from cia import __version__

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "cia",
    version=__version__,
    description=(
        "Change Impact Analyzer -- predict the impact of code changes, "
        "score risk, query dependency graphs, and predict affected tests."
    ),
)

# ---------------------------------------------------------------------------
# Internal helpers (reuse CIA library directly)
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".tox",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
    ".egg-info",
}


def _resolve_path(path: str | None) -> Path:
    """Resolve a user-supplied path or default to cwd."""
    return Path(path).resolve() if path else Path.cwd().resolve()


def _build_graph(repo_path: Path) -> Any:
    """Parse all .py files and build a DependencyGraph."""
    from cia.graph.dependency_graph import DependencyGraph
    from cia.parser.python_parser import PythonParser

    parser = PythonParser()
    py_files = sorted(
        p
        for p in repo_path.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in p.parts)
    )
    modules = []
    for pf in py_files:
        with contextlib.suppress(Exception):
            modules.append(parser.parse_file(pf))
    graph = DependencyGraph()
    graph.build_from_modules(modules)
    return graph


def _detect_changes(
    repo_path: Path,
    *,
    staged: bool = True,
    commit_range: str | None = None,
) -> Any:
    """Detect changes using CIA's ChangeDetector."""
    from cia.analyzer.change_detector import ChangeDetector
    from cia.git.git_integration import GitIntegration

    git = GitIntegration(repo_path)
    if not git.is_git_repository():
        raise ValueError(f"Not a Git repository: {repo_path}")
    detector = ChangeDetector()
    if commit_range:
        return detector.detect_changes_for_range(git, commit_range)
    return detector.detect_changes(git, staged=staged)


def _approximate_coverage(repo_path: Path, graph: Any) -> dict[str, float]:
    """Build a rough coverage map from test-file imports."""
    from cia.analyzer.test_analyzer import TestAnalyzer

    ta = TestAnalyzer()
    mapping = ta.build_test_mapping(repo_path, graph)
    covered: set[str] = set()
    for m in mapping.values():
        covered.update(m.covered_modules)
    return {mod: 60.0 if mod in covered else 0.0 for mod in graph.get_all_modules()}


def _extract_changed_symbols(
    changeset: Any,
    repo_path: Path,
) -> list[dict[str, str]]:
    """Extract changed symbols from diff."""
    import ast

    symbols: list[dict[str, str]] = []
    for change in changeset.changes:
        if not str(change.file_path).endswith(".py"):
            continue
        abs_path = repo_path / change.file_path
        if not abs_path.exists():
            continue
        try:
            source = abs_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(abs_path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        changed_lines = set(change.added_lines)
        module_stem = change.file_path.stem
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                ln in changed_lines
                for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1)
            ):
                sym_type = "function"
                qual = f"{module_stem}::{node.name}"
                for cls_node in ast.walk(tree):
                    if (
                        isinstance(cls_node, ast.ClassDef)
                        and node in ast.walk(cls_node)
                        and node is not cls_node
                    ):
                        qual = f"{module_stem}::{cls_node.name}.{node.name}"
                        sym_type = "method"
                        break
                symbols.append(
                    {
                        "module": module_stem,
                        "name": node.name,
                        "qualified_name": qual,
                        "symbol_type": sym_type,
                    }
                )
    return symbols


# ===================================================================
# MCP TOOLS
# ===================================================================


@mcp.tool()
def cia_analyze(
    path: str = ".",
    unstaged: bool = False,
    commit_range: str | None = None,
    threshold: int | None = None,
    explain: bool = True,
) -> str:
    """Analyze the impact of code changes and return a risk report.

    Runs CIA's full analysis pipeline: detect changes, build dependency
    graph, score risk, and generate an impact report.

    Args:
        path: Repository path (default: current directory).
        unstaged: If True, analyze unstaged changes instead of staged.
        commit_range: Analyze a specific commit range (e.g. HEAD~3..HEAD).
        threshold: Optional risk threshold -- report includes a warning if exceeded.
        explain: Include detailed risk factor breakdown (default: True).
    """
    from cia.analyzer.impact_analyzer import ImpactAnalyzer
    from cia.risk.risk_scorer import RiskScorer

    repo_path = _resolve_path(path)
    changeset = _detect_changes(
        repo_path, staged=not unstaged, commit_range=commit_range
    )
    dep_graph = _build_graph(repo_path)
    coverage_data = _approximate_coverage(repo_path, dep_graph)

    scorer = RiskScorer()
    risk = scorer.calculate_risk(
        changeset, graph=dep_graph, coverage_data=coverage_data
    )

    analyzer = ImpactAnalyzer(dep_graph)
    report = analyzer.analyze_change_set(changeset, risk_score=risk)
    result = report.to_dict()

    if explain:
        result["risk_explanations"] = risk.explanations
        result["risk_suggestions"] = risk.suggestions
        result["risk_factor_scores"] = {
            k: round(v, 1) for k, v in risk.factor_scores.items()
        }

    if threshold is not None and risk.overall_score > threshold:
        result["threshold_exceeded"] = True
        result["threshold"] = threshold

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def cia_detect_changes(
    path: str = ".",
    unstaged: bool = False,
    commit_range: str | None = None,
) -> str:
    """Detect changed files and symbols in the repository.

    Returns the list of changed files, their types (added/modified/deleted),
    and the specific symbols (functions/methods) that were modified.

    Args:
        path: Repository path.
        unstaged: If True, detect unstaged changes.
        commit_range: Detect changes in a commit range.
    """
    repo_path = _resolve_path(path)
    changeset = _detect_changes(
        repo_path, staged=not unstaged, commit_range=commit_range
    )
    symbols = _extract_changed_symbols(changeset, repo_path)
    result = {
        "files_changed": len(changeset.changes),
        "added": [str(p) for p in changeset.added],
        "modified": [str(p) for p in changeset.modified],
        "deleted": [str(p) for p in changeset.deleted],
        "renamed": [[str(a), str(b)] for a, b in changeset.renamed],
        "changed_symbols": symbols,
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def cia_graph(
    path: str = ".",
    output_format: str = "json",
) -> str:
    """Build and return the project's dependency graph.

    Args:
        path: Repository path.
        output_format: Output format -- 'json', 'text', or 'dot' (Graphviz).
    """
    repo_path = _resolve_path(path)
    dep_graph = _build_graph(repo_path)

    if dep_graph.module_count == 0:
        return json.dumps(
            {"modules": {}, "dependencies": [], "summary": "No Python modules found."}
        )

    cycles = dep_graph.find_cycles()

    if output_format == "json":
        data = json.loads(dep_graph.to_json())
        data["summary"] = {
            "module_count": dep_graph.module_count,
            "edge_count": dep_graph.dependency_count,
            "cycles": len(cycles),
        }
        return json.dumps(data, indent=2)
    elif output_format == "dot":
        lines = ["digraph dependencies {", "  rankdir=LR;"]
        for module in sorted(dep_graph.get_all_modules()):
            lines.append(f'  "{module}";')
        for module in sorted(dep_graph.get_all_modules()):
            for dep in sorted(dep_graph.get_dependencies(module)):
                lines.append(f'  "{module}" -> "{dep}";')
        lines.append("}")
        return "\n".join(lines)
    else:
        lines = []
        for module in sorted(dep_graph.get_all_modules()):
            deps = dep_graph.get_dependencies(module)
            dependents = dep_graph.get_dependents(module)
            lines.append(module)
            if deps:
                lines.append(f"  imports: {', '.join(sorted(deps))}")
            if dependents:
                lines.append(f"  used by: {', '.join(sorted(dependents))}")
        lines.append(
            f"\n{dep_graph.module_count} modules, {dep_graph.dependency_count} edges"
        )
        if cycles:
            lines.append(f"{len(cycles)} circular dependency(ies) detected")
        return "\n".join(lines)


@mcp.tool()
def cia_get_dependents(
    module: str,
    path: str = ".",
    transitive: bool = False,
) -> str:
    """Find all modules that depend on a given module.

    Args:
        module: The module name to look up.
        path: Repository path.
        transitive: If True, include transitive (indirect) dependents.
    """
    repo_path = _resolve_path(path)
    dep_graph = _build_graph(repo_path)

    direct = dep_graph.get_dependents(module)
    result: dict[str, Any] = {
        "module": module,
        "direct_dependents": sorted(direct),
        "direct_count": len(direct),
    }
    if transitive:
        trans = dep_graph.get_transitive_dependents(module)
        result["transitive_dependents"] = sorted(trans - set(direct))
        result["total_count"] = len(trans)
    return json.dumps(result, indent=2)


@mcp.tool()
def cia_get_dependencies(
    module: str,
    path: str = ".",
    transitive: bool = False,
) -> str:
    """Find all modules that a given module depends on (imports).

    Args:
        module: The module name to look up.
        path: Repository path.
        transitive: If True, include transitive (indirect) dependencies.
    """
    repo_path = _resolve_path(path)
    dep_graph = _build_graph(repo_path)

    direct = dep_graph.get_dependencies(module)
    result: dict[str, Any] = {
        "module": module,
        "direct_dependencies": sorted(direct),
        "direct_count": len(direct),
    }
    if transitive:
        trans = dep_graph.get_transitive_dependencies(module)
        result["transitive_dependencies"] = sorted(trans - set(direct))
        result["total_count"] = len(trans)
    return json.dumps(result, indent=2)


@mcp.tool()
def cia_predict_tests(
    path: str = ".",
    unstaged: bool = False,
    commit_range: str | None = None,
) -> str:
    """Predict which tests are affected by the current changes.

    Uses CIA's test analyzer to map changed modules to test files,
    including transitive dependents.

    Args:
        path: Repository path.
        unstaged: If True, analyze unstaged changes.
        commit_range: Analyze a specific commit range.
    """
    from cia.analyzer.test_analyzer import TestAnalyzer

    repo_path = _resolve_path(path)
    changeset = _detect_changes(
        repo_path, staged=not unstaged, commit_range=commit_range
    )
    dep_graph = _build_graph(repo_path)

    ta = TestAnalyzer()
    test_mapping = ta.build_test_mapping(repo_path, dep_graph)

    changed_modules = [c.file_path.stem for c in changeset.changes]
    expanded: set[str] = set(changed_modules)
    for mod in changed_modules:
        expanded.update(dep_graph.get_transitive_dependents(mod))
    affected = ta.predict_affected_tests(sorted(expanded), test_mapping)

    result: dict[str, Any] = {
        "affected_tests": [str(t) for t in affected],
        "count": len(affected),
    }
    if affected:
        result["pytest_expression"] = ta.generate_pytest_expression(affected)
        result["pytest_args"] = ta.generate_pytest_args(affected)
    return json.dumps(result, indent=2)


@mcp.tool()
def cia_suggest_tests(
    path: str = ".",
    unstaged: bool = False,
    commit_range: str | None = None,
) -> str:
    """Find changed code that lacks test coverage and suggest new tests.

    CIA identifies WHAT is untested; you write the tests.

    Args:
        path: Repository path.
        unstaged: If True, analyze unstaged changes.
        commit_range: Analyze a specific commit range.
    """
    from cia.analyzer.test_analyzer import TestAnalyzer

    repo_path = _resolve_path(path)
    changeset = _detect_changes(
        repo_path, staged=not unstaged, commit_range=commit_range
    )
    dep_graph = _build_graph(repo_path)

    ta = TestAnalyzer()
    test_mapping = ta.build_test_mapping(repo_path, dep_graph)
    changed_modules = [c.file_path.stem for c in changeset.changes]
    changed_symbols = _extract_changed_symbols(changeset, repo_path) or None

    suggestions = ta.suggest_missing_tests(
        changed_modules,
        test_mapping=test_mapping,
        changed_symbols=changed_symbols,
    )
    result = {
        "suggestions": [
            {
                "entity": s.entity,
                "reason": s.reason,
                "suggested_file": s.suggested_file,
            }
            for s in suggestions
        ],
        "count": len(suggestions),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def cia_score_risk(
    files: list[str],
    path: str = ".",
) -> str:
    """Score the risk of specific files without running full analysis.

    Args:
        files: List of file paths to evaluate.
        path: Repository path.
    """
    from cia.analyzer.change_detector import Change, ChangeSet
    from cia.risk.risk_scorer import RiskScorer

    repo_path = _resolve_path(path)
    dep_graph = _build_graph(repo_path)
    coverage_data = _approximate_coverage(repo_path, dep_graph)

    changes = [Change(file_path=Path(f), change_type="modified") for f in files]
    changeset = ChangeSet(changes=changes, modified=[Path(f) for f in files])

    scorer = RiskScorer()
    risk = scorer.calculate_risk(
        changeset, graph=dep_graph, coverage_data=coverage_data
    )

    return json.dumps(
        {
            "overall_score": round(risk.overall_score, 1),
            "level": risk.level,
            "factor_scores": {k: round(v, 1) for k, v in risk.factor_scores.items()},
            "explanations": risk.explanations,
            "suggestions": risk.suggestions,
        },
        indent=2,
    )


@mcp.tool()
def cia_init(path: str = ".") -> str:
    """Initialize CIA in a project directory by creating a .ciarc config file.

    Args:
        path: Project root directory.
    """
    from cia.config import DEFAULT_CIARC_CONTENT

    target = _resolve_path(path)
    rc_path = target / ".ciarc"
    if rc_path.exists():
        return json.dumps({"status": "exists", "path": str(rc_path)})
    rc_path.write_text(DEFAULT_CIARC_CONTENT, encoding="utf-8")
    return json.dumps({"status": "created", "path": str(rc_path)})


@mcp.tool()
def cia_config_get(
    key: str | None = None,
    path: str = ".",
) -> str:
    """Read CIA configuration values.

    Args:
        key: Config key (e.g. 'format'). None returns all.
        path: Project root directory.
    """
    from cia.config import find_config_file, get_config_value, load_config

    target = _resolve_path(path)
    cfg = load_config(target)
    rc = find_config_file(target)

    if key:
        val = get_config_value(cfg, key)
        return json.dumps(
            {"key": key, "value": val, "config_file": str(rc) if rc else None}
        )

    return json.dumps(
        {"config": cfg, "config_file": str(rc) if rc else None},
        indent=2,
        default=str,
    )


@mcp.tool()
def cia_config_set(
    key: str,
    value: str,
    path: str = ".",
) -> str:
    """Set a CIA configuration value. Creates .ciarc if it doesn't exist.

    Args:
        key: Config key (e.g. 'analysis.format', 'hook.block_on').
        value: New value.
        path: Project root directory.
    """
    from cia.config import find_config_file, set_config_value

    target = _resolve_path(path)
    rc = find_config_file(target)
    if rc is None:
        rc = target / ".ciarc"
    set_config_value(rc, key.strip(), value.strip())
    return json.dumps({"status": "ok", "key": key, "value": value, "file": str(rc)})


# ===================================================================
# MCP RESOURCES
# ===================================================================


@mcp.resource("cia://version")
def resource_version() -> str:
    """CIA version and environment information."""
    return json.dumps(
        {
            "version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        indent=2,
    )


@mcp.resource("cia://config")
def resource_config() -> str:
    """Current effective CIA configuration."""
    from cia.config import find_config_file, load_config

    cfg = load_config()
    rc = find_config_file()
    return json.dumps(
        {"config": cfg, "config_file": str(rc) if rc else None},
        indent=2,
        default=str,
    )


@mcp.resource("cia://risk/weights")
def resource_risk_weights() -> str:
    """Current risk factor weights."""
    from cia.risk.risk_factors import DEFAULT_WEIGHTS

    return json.dumps(dict(DEFAULT_WEIGHTS), indent=2)


@mcp.resource("cia://risk/thresholds")
def resource_risk_thresholds() -> str:
    """Score-to-level mapping for risk levels."""
    return json.dumps(
        {
            "low": "0-25",
            "medium": "26-50",
            "high": "51-75",
            "critical": "76-100",
        },
        indent=2,
    )


# ===================================================================
# MCP PROMPTS
# ===================================================================


@mcp.prompt()
def pre_commit_review(path: str = ".") -> str:
    """Full pre-commit review: risk score + affected tests + coverage gaps.

    Run CIA's analyze, predict_tests, and suggest_tests tools, then
    synthesize a structured review with a go/no-go verdict.
    """
    return (
        f"Analyze the staged changes in the repository at '{path}' using CIA tools.\n\n"
        "1. Call `cia_analyze` to get the risk score and factor breakdown.\n"
        "2. Call `cia_predict_tests` to find which tests are affected.\n"
        "3. Call `cia_suggest_tests` to find coverage gaps.\n\n"
        "Then synthesize a Pre-Commit Review with these sections:\n"
        "- **Risk Score**: overall score, level, and top contributing factors\n"
        "- **Blast Radius**: number of affected modules\n"
        "- **Tests to Run**: the pytest command from CIA's output\n"
        "- **Coverage Gaps**: entities CIA flagged as untested\n"
        "- **Verdict**: LOW (safe) / MEDIUM (run tests) "
        "/ HIGH (add tests or split commit)\n"
    )


@mcp.prompt()
def blast_radius(module: str, path: str = ".") -> str:
    """Analyze the blast radius of a module -- what breaks if you change it.

    Uses CIA's dependency graph to find all downstream dependents.
    """
    return (
        f"Analyze the blast radius of module '{module}' "
        f"in '{path}' using CIA tools.\n\n"
        f"1. Call `cia_get_dependents` with module='{module}' and transitive=true.\n"
        f"2. Call `cia_graph` with output_format='json' to get the full graph.\n\n"
        "Present the results as:\n"
        "- Direct dependents (depth 1)\n"
        "- Transitive dependents (depth 2+), grouped by depth\n"
        "- Total count\n"
        "- Risk assessment: how dangerous is it to change this module?\n"
        "- Which tests are affected\n"
    )


@mcp.prompt()
def test_gap_analysis(path: str = ".") -> str:
    """Find untested code in staged changes and write the missing tests.

    CIA identifies what is untested; you write the pytest skeletons.
    """
    return (
        f"Find test coverage gaps in the staged changes at '{path}' using CIA.\n\n"
        "1. Call `cia_suggest_tests` to get CIA's coverage gap report.\n"
        "2. If CIA reports no gaps, say 'All changed code has test coverage.'\n"
        "3. For each entity CIA flagged as untested:\n"
        "   a. Read the source file containing the entity.\n"
        "   b. Write a pytest test class with a happy-path test, an edge-case test,\n"
        "      and an error-handling test.\n"
        "   c. Place it in the file path CIA suggested.\n"
        "4. Show the generated test code.\n"
    )


@mcp.prompt()
def dependency_audit(path: str = ".") -> str:
    """Architecture health audit using CIA's dependency graph.

    Checks for circular dependencies, god modules, orphans, and depth.
    """
    return (
        f"Audit the architecture of the project at '{path}' using CIA.\n\n"
        "1. Call `cia_graph` with output_format='json' to get CIA's dependency data.\n"
        "2. Analyze for:\n"
        "   - Circular dependencies (cycles in CIA's graph)\n"
        "   - God modules (fan-in > 10 from CIA's edges)\n"
        "   - Orphan modules (0 edges in CIA's graph)\n"
        "   - Max dependency depth\n"
        "3. Score project health from A (excellent) to F (poor).\n"
        "4. For each issue, cite CIA's data and provide a recommendation.\n"
    )


@mcp.prompt()
def safe_refactor(symbol: str, path: str = ".") -> str:
    """CIA-guided safe refactoring with verification.

    Uses CIA's graph and test data to build a refactoring checklist.
    """
    return (
        f"Help refactor '{symbol}' in '{path}' safely using CIA data.\n\n"
        f"1. Call `cia_get_dependents` to find everything that references '{symbol}'.\n"
        "2. Call `cia_graph` to understand the exact import paths.\n"
        "3. Build a refactoring checklist:\n"
        "   - Every file that imports the symbol (from CIA's graph)\n"
        "   - Every test that covers it (from CIA's test data)\n"
        "   - Risk score for the refactor\n"
        "4. Guide the refactoring step by step.\n"
        "5. After changes, run `cia_predict_tests` and verify.\n"
    )


@mcp.prompt()
def pr_summary(path: str = ".") -> str:
    """Generate a PR description from CIA's analysis of current changes."""
    return (
        f"Generate a PR description for the changes in '{path}' using CIA.\n\n"
        "1. Call `cia_analyze` to get the risk report.\n"
        "2. Call `cia_detect_changes` to get the changed files and symbols.\n"
        "3. Call `cia_predict_tests` to get affected tests.\n\n"
        "Write a structured PR description with:\n"
        "- **Summary**: what changed (module-by-module)\n"
        "- **Risk**: CIA's score and level\n"
        "- **Impact**: blast radius from CIA's data\n"
        "- **Tests**: which tests cover this change\n"
        "- **Coverage**: any gaps CIA found\n"
    )


@mcp.prompt()
def risk_explanation(path: str = ".") -> str:
    """Explain CIA's risk scores in detail for the current changes."""
    return (
        f"Explain the risk of the current changes in '{path}' using CIA.\n\n"
        "1. Call `cia_analyze` with explain=true.\n"
        "2. For each risk factor in CIA's output:\n"
        "   - Explain what the factor measures\n"
        "   - Show its score and weight\n"
        "   - Explain why it scored that way\n"
        "3. Identify the biggest risk driver.\n"
        "4. Suggest concrete mitigations from CIA's suggestions.\n"
    )


# ===================================================================
# Entry point
# ===================================================================


def create_server() -> FastMCP:
    """Return the configured MCP server instance."""
    return mcp


def main() -> None:
    """CLI entry point for cia-mcp."""
    transport = "stdio"
    port = 8080

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--transport", "-t") and i + 1 < len(args):
            transport = args[i + 1]
            i += 2
        elif args[i] in ("--port", "-p") and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] in ("--help", "-h"):
            print("Usage: cia-mcp [--transport stdio|sse] [--port PORT]")
            print()
            print("Start the CIA MCP server.")
            print()
            print("Options:")
            print("  --transport, -t   Transport type: stdio (default) or sse")
            print("  --port, -p        Port for SSE transport (default: 8080)")
            sys.exit(0)
        else:
            i += 1

    if transport == "sse":
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
