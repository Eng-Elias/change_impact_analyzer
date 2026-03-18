"""Risk scoring engine that combines risk factors into an overall score."""

from __future__ import annotations

import networkx as nx

from cia.analyzer.change_detector import Change, ChangeSet
from cia.graph.dependency_graph import DependencyGraph
from cia.risk.risk_factors import (
    DEFAULT_WEIGHTS,
    RiskFactorType,
    RiskScore,
    score_to_level,
)


class RiskScorer:
    """Scores the risk of code changes based on multiple weighted factors.

    Each individual factor method returns a raw score in the range **0–100**.
    :meth:`combine_scores` multiplies each by its weight and sums them to
    produce the overall 0–100 score.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._weights = weights or dict(DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def calculate_risk(
        self,
        change_set: ChangeSet,
        graph: DependencyGraph | None = None,
        git_history: list[str] | None = None,
        *,
        coverage_data: dict[str, float] | None = None,
    ) -> RiskScore:
        """Calculate the overall risk for a *ChangeSet*.

        Parameters
        ----------
        change_set:
            The set of detected changes.
        graph:
            Module-level dependency graph (used for *dependents* and
            *critical_path* factors).
        git_history:
            Flat list of file paths that have changed in recent commits
            (used for *churn* factor).
        coverage_data:
            Mapping of file-path stems to coverage percentages 0–100
            (used for *test_coverage* factor).
        """
        factor_scores: dict[str, float] = {}

        # --- complexity ---
        factor_scores[RiskFactorType.COMPLEXITY] = self.score_complexity(
            change_set.changes
        )

        # --- churn ---
        churn_scores: list[float] = []
        for change in change_set.changes:
            churn_scores.append(
                self.score_churn(str(change.file_path), git_history or [])
            )
        factor_scores[RiskFactorType.CHURN] = (
            max(churn_scores) if churn_scores else 0.0
        )

        # --- dependents ---
        factor_scores[RiskFactorType.DEPENDENTS] = self.score_dependents(
            change_set.changes, graph
        )

        # --- test coverage ---
        factor_scores[RiskFactorType.TEST_COVERAGE] = self.score_test_coverage(
            change_set.changes, coverage_data or {}
        )

        # --- change size ---
        factor_scores[RiskFactorType.CHANGE_SIZE] = self.score_change_size(
            change_set.changes
        )

        # --- critical path ---
        factor_scores[RiskFactorType.CRITICAL_PATH] = self.score_critical_path(
            change_set.changes, graph
        )

        overall = self.combine_scores(factor_scores, self._weights)
        level = score_to_level(overall)

        explanations = self._build_explanations(factor_scores)
        suggestions = self._build_suggestions(factor_scores, change_set)

        return RiskScore(
            overall_score=round(overall, 2),
            level=level,
            factor_scores={
                k.value if hasattr(k, "value") else k: round(v, 2)
                for k, v in factor_scores.items()
            },
            explanations=explanations,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Individual factor scoring (each returns 0–100)
    # ------------------------------------------------------------------

    @staticmethod
    def score_complexity(changes: list[Change]) -> float:
        """Score complexity based on the number of affected symbols.

        A rough proxy: more affected symbols → higher complexity.
        """
        total_symbols = sum(len(c.affected_symbols) for c in changes)
        return min(total_symbols * 10.0, 100.0)

    @staticmethod
    def score_churn(filepath: str, git_history: list[str]) -> float:
        """Score churn based on how often *filepath* appears in recent history.

        *git_history* is a flat list of file paths from recent commits.
        """
        if not git_history:
            return 0.0
        count = sum(1 for p in git_history if p == filepath)
        return min(count * 10.0, 100.0)

    @staticmethod
    def score_dependents(
        changes: list[Change],
        graph: DependencyGraph | None,
    ) -> float:
        """Score based on the number of downstream dependents."""
        if graph is None:
            return 0.0
        total = 0
        for change in changes:
            module = change.file_path.stem
            total += len(graph.get_dependents(module))
        return min(total * 10.0, 100.0)

    @staticmethod
    def score_test_coverage(
        changes: list[Change],
        coverage_data: dict[str, float],
    ) -> float:
        """Score based on **lack** of test coverage.

        Higher score = less coverage = more risk.  If no coverage data
        is available for a file, it is assumed uncovered (score 80).
        """
        if not changes:
            return 0.0
        scores: list[float] = []
        for change in changes:
            key = change.file_path.stem
            cov = coverage_data.get(key)
            if cov is None:
                scores.append(80.0)
            else:
                scores.append(max(0.0, 100.0 - cov))
        return sum(scores) / len(scores)

    @staticmethod
    def score_change_size(changes: list[Change]) -> float:
        """Score based on total lines added + deleted."""
        total = sum(
            len(c.added_lines) + len(c.deleted_lines) for c in changes
        )
        return min(total * 0.5, 100.0)

    @staticmethod
    def score_critical_path(
        changes: list[Change],
        graph: DependencyGraph | None,
    ) -> float:
        """Score based on betweenness centrality in the dependency graph."""
        if graph is None or graph.module_count == 0:
            return 0.0
        centralities = nx.betweenness_centrality(graph.graph)
        max_cent = 0.0
        for change in changes:
            module = change.file_path.stem
            cent = centralities.get(module, 0.0)
            if cent > max_cent:
                max_cent = cent
        return min(max_cent * 100.0, 100.0)

    # ------------------------------------------------------------------
    # Score combination
    # ------------------------------------------------------------------

    @staticmethod
    def combine_scores(
        factor_scores: dict[str, float],
        weights: dict[str, float],
    ) -> float:
        """Combine individual 0–100 factor scores using *weights*.

        Returns a weighted sum in the range 0–100.
        """
        total = 0.0
        for key, score in factor_scores.items():
            w = weights.get(key, 0.0)
            total += w * score
        return min(total, 100.0)

    # ------------------------------------------------------------------
    # Explainability
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanations(factor_scores: dict[str, float]) -> list[str]:
        """Generate human-readable explanations sorted by contribution."""
        _labels = {
            RiskFactorType.COMPLEXITY: "Complexity of changed code",
            RiskFactorType.CHURN: "File churn (recent change frequency)",
            RiskFactorType.DEPENDENTS: "Number of downstream dependents",
            RiskFactorType.TEST_COVERAGE: "Lack of test coverage",
            RiskFactorType.CHANGE_SIZE: "Size of the change (lines)",
            RiskFactorType.CRITICAL_PATH: "Position on critical path",
        }
        sorted_factors = sorted(
            factor_scores.items(), key=lambda kv: kv[1], reverse=True
        )
        lines: list[str] = []
        for key, score in sorted_factors:
            enum_key = RiskFactorType(key) if isinstance(key, str) else key
            label = _labels.get(enum_key, str(key))
            lines.append(f"{label}: {score:.0f}/100")
        return lines

    @staticmethod
    def _build_suggestions(
        factor_scores: dict[str, float],
        change_set: ChangeSet,
    ) -> list[str]:
        """Suggest concrete actions based on the highest-risk factors."""
        suggestions: list[str] = []

        cov_score = factor_scores.get(RiskFactorType.TEST_COVERAGE, 0.0)
        if cov_score >= 50:
            for c in change_set.changes:
                for sym in c.affected_symbols:
                    suggestions.append(
                        f"Add tests for modified {sym.symbol_type} "
                        f"'{sym.name}' in {c.file_path}"
                    )
            if not suggestions:
                suggestions.append("Add tests for the modified files")

        dep_score = factor_scores.get(RiskFactorType.DEPENDENTS, 0.0)
        if dep_score >= 50:
            suggestions.append(
                "Consider notifying owners of downstream dependent modules"
            )

        size_score = factor_scores.get(RiskFactorType.CHANGE_SIZE, 0.0)
        if size_score >= 50:
            suggestions.append("Consider splitting this change into smaller commits")

        complexity_score = factor_scores.get(RiskFactorType.COMPLEXITY, 0.0)
        if complexity_score >= 50:
            suggestions.append(
                "Review the affected symbols carefully — high complexity detected"
            )

        return suggestions
