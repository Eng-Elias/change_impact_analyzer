"""Risk scoring engine that combines risk factors into an overall score."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from cia.analyzer.impact_analyzer import AnalysisReport, ImpactResult
from cia.graph.dependency_graph import DependencyGraph
from cia.risk.risk_factors import RiskFactors, RiskLevel


@dataclass
class RiskAssessment:
    """Risk assessment for a single change impact."""

    impact: ImpactResult
    score: float
    level: RiskLevel
    factors: RiskFactors


class RiskScorer:
    """Scores the risk of code changes based on multiple risk factors."""

    def __init__(self, dependency_graph: DependencyGraph) -> None:
        self._dep_graph = dependency_graph

    def score_report(self, report: AnalysisReport) -> list[RiskAssessment]:
        """Score all impacts in an analysis report."""
        return [self._score_impact(impact) for impact in report.impacts]

    def _score_impact(self, impact: ImpactResult) -> RiskAssessment:
        """Calculate the risk score for a single impact result."""
        factors = RiskFactors()

        dep_count = len(impact.directly_affected)
        factors.set_value("dependency_count", min(dep_count / 10.0, 1.0))

        trans_count = len(impact.transitively_affected)
        factors.set_value("transitive_reach", min(trans_count / 20.0, 1.0))

        change_size = len(impact.change.added_lines) + len(impact.change.deleted_lines)
        factors.set_value("change_size", min(change_size / 100.0, 1.0))

        module_name = impact.change.file_path.stem
        centrality = self._compute_centrality(module_name)
        factors.set_value("centrality", centrality)

        score = factors.total_score()
        level = self._score_to_level(score)

        return RiskAssessment(
            impact=impact,
            score=score,
            level=level,
            factors=factors,
        )

    def _compute_centrality(self, module_name: str) -> float:
        """Compute the betweenness centrality of a module in the dependency graph."""
        graph = self._dep_graph.graph
        if module_name not in graph:
            return 0.0
        centralities = nx.betweenness_centrality(graph)
        return centralities.get(module_name, 0.0)

    @staticmethod
    def _score_to_level(score: float) -> RiskLevel:
        """Convert a numeric risk score to a risk level."""
        if score >= 0.75:
            return RiskLevel.CRITICAL
        if score >= 0.50:
            return RiskLevel.HIGH
        if score >= 0.25:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
