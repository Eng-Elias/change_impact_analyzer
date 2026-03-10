"""Core impact analysis engine combining graphs and change detection."""

from __future__ import annotations

from dataclasses import dataclass, field

from cia.analyzer.change_detector import Change
from cia.graph.call_graph import CallGraph
from cia.graph.dependency_graph import DependencyGraph


@dataclass
class ImpactResult:
    """Result of an impact analysis for a single change."""

    change: Change
    directly_affected: list[str] = field(default_factory=list)
    transitively_affected: list[str] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    """Complete impact analysis report."""

    impacts: list[ImpactResult] = field(default_factory=list)
    total_files_changed: int = 0
    total_symbols_affected: int = 0
    total_modules_affected: int = 0


class ImpactAnalyzer:
    """Analyzes the impact of code changes using dependency and call graphs."""

    def __init__(
        self,
        dependency_graph: DependencyGraph,
        call_graph: CallGraph,
    ) -> None:
        self._dep_graph = dependency_graph
        self._call_graph = call_graph

    def analyze(self, changes: list[Change]) -> AnalysisReport:
        """Perform impact analysis on a list of changes."""
        report = AnalysisReport()
        all_affected_modules: set[str] = set()

        for change in changes:
            impact = self._analyze_single_change(change)
            report.impacts.append(impact)
            all_affected_modules.update(impact.affected_modules)

        report.total_files_changed = len(changes)
        report.total_symbols_affected = sum(
            len(i.directly_affected) + len(i.transitively_affected)
            for i in report.impacts
        )
        report.total_modules_affected = len(all_affected_modules)
        return report

    def _analyze_single_change(self, change: Change) -> ImpactResult:
        """Analyze the impact of a single change."""
        result = ImpactResult(change=change)

        for symbol in change.affected_symbols:
            callers = self._call_graph.get_callers(symbol.qualified_name)
            result.directly_affected.extend(callers)

            transitive = self._call_graph.get_transitive_callers(
                symbol.qualified_name
            )
            result.transitively_affected.extend(
                t for t in transitive if t not in callers
            )

        module_name = change.file_path.stem
        dependents = self._dep_graph.get_transitive_dependents(module_name)
        result.affected_modules = list(dependents)

        return result
