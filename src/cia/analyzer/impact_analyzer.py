"""Core impact analysis engine combining graphs and change detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cia.analyzer.change_detector import Change, ChangeSet
from cia.graph.call_graph import CallGraph
from cia.graph.dependency_graph import DependencyGraph
from cia.risk.risk_factors import RiskLevel, RiskScore

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


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


@dataclass
class ImpactReport:
    """Full orchestrated report combining all analysis dimensions."""

    analysis: AnalysisReport = field(default_factory=AnalysisReport)
    risk: RiskScore | None = None
    affected_tests: list[Path] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON output."""
        d: dict[str, Any] = {
            "total_files_changed": self.analysis.total_files_changed,
            "total_symbols_affected": self.analysis.total_symbols_affected,
            "total_modules_affected": self.analysis.total_modules_affected,
            "affected_modules": self.affected_modules,
            "affected_tests": [str(t) for t in self.affected_tests],
            "recommendations": self.recommendations,
        }
        if self.risk is not None:
            d["risk_score"] = self.risk.overall_score
            d["risk_level"] = self.risk.level.value
            d["risk_explanations"] = self.risk.explanations
            d["risk_suggestions"] = self.risk.suggestions
        return d


# ---------------------------------------------------------------------------
# ImpactAnalyzer
# ---------------------------------------------------------------------------


class ImpactAnalyzer:
    """Analyzes the impact of code changes using dependency and call graphs.

    Also serves as the **orchestrator** that coordinates graph analysis,
    risk scoring, test-impact prediction, and recommendation generation.
    """

    def __init__(
        self,
        dependency_graph: DependencyGraph,
        call_graph: CallGraph | None = None,
    ) -> None:
        self._dep_graph = dependency_graph
        self._call_graph = call_graph or CallGraph()

    # ------------------------------------------------------------------
    # Core per-change analysis
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Orchestrator: full change-set analysis
    # ------------------------------------------------------------------

    def analyze_change_set(
        self,
        change_set: ChangeSet,
        *,
        risk_score: RiskScore | None = None,
        affected_tests: list[Path] | None = None,
    ) -> ImpactReport:
        """Analyse a *ChangeSet* and produce a full *ImpactReport*.

        Parameters
        ----------
        change_set:
            Detected changes to evaluate.
        risk_score:
            Pre-computed risk score (optional).
        affected_tests:
            Pre-computed affected test files (optional).
        """
        analysis = self.analyze(change_set.changes)
        affected_modules = self.combine_graph_analysis(
            self._dep_graph, change_set.changes
        )
        recommendations = self.generate_recommendations(
            analysis, risk_score, affected_modules
        )

        return ImpactReport(
            analysis=analysis,
            risk=risk_score,
            affected_tests=affected_tests or [],
            recommendations=recommendations,
            affected_modules=affected_modules,
        )

    # ------------------------------------------------------------------
    # Combination helpers
    # ------------------------------------------------------------------

    @staticmethod
    def combine_graph_analysis(
        graph: DependencyGraph,
        changes: list[Change],
    ) -> list[str]:
        """Return a de-duplicated list of all affected module names."""
        affected: set[str] = set()
        for change in changes:
            module = change.file_path.stem
            affected.add(module)
            affected.update(graph.get_dependents(module))
            affected.update(graph.get_transitive_dependents(module))
        return sorted(affected)

    @staticmethod
    def combine_risk_analysis(risk_scores: list[RiskScore]) -> RiskScore:
        """Combine multiple *RiskScore* objects into one overall assessment.

        Uses the **maximum** overall score and the highest level.
        """
        if not risk_scores:
            return RiskScore()

        max_score = max(r.overall_score for r in risk_scores)
        max_level = max(
            risk_scores,
            key=lambda r: ["low", "medium", "high", "critical"].index(r.level.value),
        ).level

        all_explanations: list[str] = []
        all_suggestions: list[str] = []
        merged_factors: dict[str, float] = {}
        for rs in risk_scores:
            all_explanations.extend(rs.explanations)
            all_suggestions.extend(rs.suggestions)
            for k, v in rs.factor_scores.items():
                merged_factors[k] = max(merged_factors.get(k, 0.0), v)

        return RiskScore(
            overall_score=max_score,
            level=max_level,
            factor_scores=merged_factors,
            explanations=list(dict.fromkeys(all_explanations)),
            suggestions=list(dict.fromkeys(all_suggestions)),
        )

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def generate_recommendations(
        analysis: AnalysisReport,
        risk_score: RiskScore | None = None,
        affected_modules: list[str] | None = None,
    ) -> list[str]:
        """Generate actionable recommendations based on the analysis."""
        recs: list[str] = []

        if analysis.total_modules_affected > 5:
            recs.append(
                f"Large blast radius: {analysis.total_modules_affected} "
                "modules affected — consider splitting the change."
            )

        if risk_score is not None:
            if risk_score.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                recs.append(
                    f"Risk level is {risk_score.level.value} — "
                    "thorough code review is strongly recommended."
                )
            recs.extend(risk_score.suggestions)

        if affected_modules and len(affected_modules) > 10:
            recs.append(
                "Consider adding integration tests covering the "
                f"{len(affected_modules)} affected modules."
            )

        return recs
