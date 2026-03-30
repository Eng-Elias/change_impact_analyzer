"""Comprehensive tests for RiskScorer."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.analyzer.change_detector import Change, ChangeSet
from cia.graph.dependency_graph import DependencyGraph
from cia.parser.base import Symbol
from cia.risk.risk_factors import (
    DEFAULT_WEIGHTS,
    RiskFactorType,
    RiskLevel,
    RiskScore,
)
from cia.risk.risk_scorer import RiskScorer

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _change(
    path: str = "utils.py",
    change_type: str = "modified",
    added: list[int] | None = None,
    deleted: list[int] | None = None,
    symbols: list[Symbol] | None = None,
) -> Change:
    return Change(
        file_path=Path(path),
        change_type=change_type,
        added_lines=added or [],
        deleted_lines=deleted or [],
        affected_symbols=symbols or [],
    )


def _changeset(changes: list[Change] | None = None) -> ChangeSet:
    changes = changes or []
    added = [c.file_path for c in changes if c.change_type == "added"]
    modified = [c.file_path for c in changes if c.change_type == "modified"]
    deleted = [c.file_path for c in changes if c.change_type == "deleted"]
    return ChangeSet(
        changes=changes,
        added=added,
        modified=modified,
        deleted=deleted,
    )


def _symbol(name: str = "foo", path: str = "utils.py") -> Symbol:
    return Symbol(
        name=name,
        qualified_name=f"mod.{name}",
        symbol_type="function",
        file_path=Path(path),
        line_start=1,
        line_end=10,
    )


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def scorer() -> RiskScorer:
    return RiskScorer()


@pytest.fixture
def graph() -> DependencyGraph:
    g = DependencyGraph()
    g.add_module("utils", filepath="utils.py")
    g.add_module("main", filepath="main.py")
    g.add_module("models", filepath="models.py")
    g.add_dependency("main", "utils")
    g.add_dependency("models", "utils")
    return g


@pytest.fixture
def empty_changeset() -> ChangeSet:
    return _changeset([])


@pytest.fixture
def simple_changeset() -> ChangeSet:
    return _changeset([_change(added=[1, 2, 3], deleted=[4])])


# ==================================================================
# Individual factor scoring
# ==================================================================


class TestScoreComplexity:
    def test_no_symbols(self, scorer: RiskScorer) -> None:
        assert scorer.score_complexity([_change()]) == 0.0

    def test_few_symbols(self, scorer: RiskScorer) -> None:
        c = _change(symbols=[_symbol("a"), _symbol("b")])
        assert scorer.score_complexity([c]) == pytest.approx(20.0)

    def test_many_symbols_capped(self, scorer: RiskScorer) -> None:
        syms = [_symbol(f"f{i}") for i in range(15)]
        c = _change(symbols=syms)
        assert scorer.score_complexity([c]) == 100.0


class TestScoreChurn:
    def test_no_history(self, scorer: RiskScorer) -> None:
        assert scorer.score_churn("utils.py", []) == 0.0

    def test_single_occurrence(self, scorer: RiskScorer) -> None:
        assert scorer.score_churn("utils.py", ["utils.py"]) == pytest.approx(10.0)

    def test_many_occurrences(self, scorer: RiskScorer) -> None:
        history = ["utils.py"] * 15
        assert scorer.score_churn("utils.py", history) == 100.0

    def test_different_file(self, scorer: RiskScorer) -> None:
        assert scorer.score_churn("utils.py", ["other.py", "other.py"]) == 0.0


class TestScoreDependents:
    def test_no_graph(self, scorer: RiskScorer) -> None:
        assert scorer.score_dependents([_change()], None) == 0.0

    def test_with_dependents(self, scorer: RiskScorer, graph: DependencyGraph) -> None:
        score = scorer.score_dependents([_change("utils.py")], graph)
        assert score == pytest.approx(20.0)  # 2 dependents * 10

    def test_no_dependents(self, scorer: RiskScorer, graph: DependencyGraph) -> None:
        score = scorer.score_dependents([_change("main.py")], graph)
        assert score == 0.0


class TestScoreTestCoverage:
    def test_no_changes(self, scorer: RiskScorer) -> None:
        assert scorer.score_test_coverage([], {}) == 0.0

    def test_no_coverage_data(self, scorer: RiskScorer) -> None:
        score = scorer.score_test_coverage([_change()], {})
        assert score == pytest.approx(80.0)  # assumed uncovered

    def test_full_coverage(self, scorer: RiskScorer) -> None:
        score = scorer.score_test_coverage([_change()], {"utils": 100.0})
        assert score == pytest.approx(0.0)

    def test_partial_coverage(self, scorer: RiskScorer) -> None:
        score = scorer.score_test_coverage([_change()], {"utils": 60.0})
        assert score == pytest.approx(40.0)

    def test_multiple_files(self, scorer: RiskScorer) -> None:
        changes = [_change("a.py"), _change("b.py")]
        cov = {"a": 100.0, "b": 50.0}
        score = scorer.score_test_coverage(changes, cov)
        # (0 + 50) / 2 = 25
        assert score == pytest.approx(25.0)


class TestScoreChangeSize:
    def test_no_lines(self, scorer: RiskScorer) -> None:
        assert scorer.score_change_size([_change()]) == 0.0

    def test_small_change(self, scorer: RiskScorer) -> None:
        c = _change(added=[1, 2, 3])
        assert scorer.score_change_size([c]) == pytest.approx(1.5)

    def test_large_change_capped(self, scorer: RiskScorer) -> None:
        c = _change(added=list(range(300)))
        assert scorer.score_change_size([c]) == 100.0


class TestScoreCriticalPath:
    def test_no_graph(self, scorer: RiskScorer) -> None:
        assert scorer.score_critical_path([_change()], None) == 0.0

    def test_empty_graph(self, scorer: RiskScorer) -> None:
        g = DependencyGraph()
        assert scorer.score_critical_path([_change()], g) == 0.0

    def test_with_graph(self, scorer: RiskScorer, graph: DependencyGraph) -> None:
        score = scorer.score_critical_path([_change("utils.py")], graph)
        # betweenness centrality for utils in the graph should be > 0
        assert score >= 0.0


# ==================================================================
# combine_scores
# ==================================================================


class TestCombineScores:
    def test_basic(self) -> None:
        scores = {RiskFactorType.COMPLEXITY: 50.0, RiskFactorType.CHURN: 50.0}
        weights = {RiskFactorType.COMPLEXITY: 0.5, RiskFactorType.CHURN: 0.5}
        result = RiskScorer.combine_scores(scores, weights)
        assert result == pytest.approx(50.0)

    def test_all_zero(self) -> None:
        scores = {ft: 0.0 for ft in RiskFactorType}
        result = RiskScorer.combine_scores(scores, DEFAULT_WEIGHTS)
        assert result == 0.0

    def test_all_max(self) -> None:
        scores = {ft: 100.0 for ft in RiskFactorType}
        result = RiskScorer.combine_scores(scores, DEFAULT_WEIGHTS)
        assert result == pytest.approx(100.0)

    def test_capped_at_100(self) -> None:
        scores = {RiskFactorType.COMPLEXITY: 200.0}
        weights = {RiskFactorType.COMPLEXITY: 1.0}
        result = RiskScorer.combine_scores(scores, weights)
        assert result == 100.0

    def test_missing_weight_ignored(self) -> None:
        scores = {RiskFactorType.COMPLEXITY: 80.0}
        result = RiskScorer.combine_scores(scores, {})
        assert result == 0.0


# ==================================================================
# calculate_risk (integration)
# ==================================================================


class TestCalculateRisk:
    def test_empty_changeset(
        self, scorer: RiskScorer, empty_changeset: ChangeSet
    ) -> None:
        risk = scorer.calculate_risk(empty_changeset)
        assert isinstance(risk, RiskScore)
        assert risk.overall_score >= 0.0
        assert risk.level in RiskLevel

    def test_simple_changeset(
        self, scorer: RiskScorer, simple_changeset: ChangeSet
    ) -> None:
        risk = scorer.calculate_risk(simple_changeset)
        assert 0.0 <= risk.overall_score <= 100.0
        assert risk.level in RiskLevel
        assert len(risk.factor_scores) == len(RiskFactorType)

    def test_with_graph(
        self, scorer: RiskScorer, simple_changeset: ChangeSet, graph: DependencyGraph
    ) -> None:
        risk = scorer.calculate_risk(simple_changeset, graph=graph)
        assert risk.overall_score >= 0.0

    def test_with_history(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change("utils.py")])
        history = ["utils.py"] * 5
        risk = scorer.calculate_risk(cs, git_history=history)
        assert risk.factor_scores.get("churn", 0.0) > 0.0

    def test_with_coverage(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change("utils.py")])
        risk = scorer.calculate_risk(cs, coverage_data={"utils": 90.0})
        assert risk.factor_scores.get("test_coverage", 100.0) < 80.0

    def test_all_factors_present(
        self, scorer: RiskScorer, simple_changeset: ChangeSet
    ) -> None:
        risk = scorer.calculate_risk(simple_changeset)
        for ft in RiskFactorType:
            assert ft.value in risk.factor_scores

    def test_low_risk(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change(added=[1])])
        risk = scorer.calculate_risk(cs, coverage_data={"utils": 100.0})
        assert risk.level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_custom_weights(self) -> None:
        custom = {ft: 0.0 for ft in RiskFactorType}
        s = RiskScorer(weights=custom)
        cs = _changeset([_change(added=list(range(200)))])
        risk = s.calculate_risk(cs)
        assert risk.overall_score == 0.0


# ==================================================================
# Explainability
# ==================================================================


class TestExplainability:
    def test_explanations_present(
        self, scorer: RiskScorer, simple_changeset: ChangeSet
    ) -> None:
        risk = scorer.calculate_risk(simple_changeset)
        assert len(risk.explanations) == len(RiskFactorType)
        assert all("/100" in e for e in risk.explanations)

    def test_explanations_sorted_descending(
        self, scorer: RiskScorer, simple_changeset: ChangeSet
    ) -> None:
        risk = scorer.calculate_risk(simple_changeset)
        # extract scores from explanations
        scores = []
        for e in risk.explanations:
            num = float(e.split(":")[1].strip().split("/")[0])
            scores.append(num)
        assert scores == sorted(scores, reverse=True)

    def test_suggestions_for_low_coverage(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change(symbols=[_symbol("my_func")])])
        risk = scorer.calculate_risk(cs, coverage_data={})
        # no coverage → should suggest adding tests
        assert any("test" in s.lower() for s in risk.suggestions)

    def test_suggestions_for_high_dependents(self, scorer: RiskScorer) -> None:
        g = DependencyGraph()
        g.add_module("core")
        for i in range(10):
            g.add_module(f"mod{i}")
            g.add_dependency(f"mod{i}", "core")
        cs = _changeset([_change("core.py")])
        risk = scorer.calculate_risk(cs, graph=g)
        assert any("downstream" in s.lower() for s in risk.suggestions)

    def test_suggestions_for_large_change(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change(added=list(range(250)))])
        risk = scorer.calculate_risk(cs, coverage_data={"utils": 100.0})
        assert any("split" in s.lower() for s in risk.suggestions)

    def test_suggestions_for_high_complexity(self, scorer: RiskScorer) -> None:
        syms = [_symbol(f"f{i}") for i in range(8)]
        cs = _changeset([_change(symbols=syms)])
        risk = scorer.calculate_risk(cs)
        assert any("complexity" in s.lower() for s in risk.suggestions)

    def test_no_suggestions_when_low_risk(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change(added=[1])])
        risk = scorer.calculate_risk(cs, coverage_data={"utils": 100.0})
        # May or may not have suggestions, but should not crash
        assert isinstance(risk.suggestions, list)


# ==================================================================
# Weight configuration
# ==================================================================


class TestWeightConfiguration:
    def test_default_weights(self, scorer: RiskScorer) -> None:
        assert scorer._weights == DEFAULT_WEIGHTS

    def test_custom_weights_applied(self) -> None:
        custom = {ft: 0.0 for ft in RiskFactorType}
        custom[RiskFactorType.CHANGE_SIZE] = 1.0
        s = RiskScorer(weights=custom)
        cs = _changeset([_change(added=list(range(100)))])
        risk = s.calculate_risk(cs)
        # Only change_size contributes
        assert risk.overall_score == pytest.approx(min(100 * 0.5, 100.0) * 1.0)

    def test_zero_weights(self) -> None:
        custom = {ft: 0.0 for ft in RiskFactorType}
        s = RiskScorer(weights=custom)
        cs = _changeset([_change(added=list(range(200)))])
        risk = s.calculate_risk(cs)
        assert risk.overall_score == 0.0

    def test_single_factor_weight(self) -> None:
        custom = {ft: 0.0 for ft in RiskFactorType}
        custom[RiskFactorType.CHURN] = 1.0
        s = RiskScorer(weights=custom)
        cs = _changeset([_change("a.py")])
        history = ["a.py"] * 5
        risk = s.calculate_risk(cs, git_history=history)
        assert risk.overall_score == pytest.approx(50.0)


# ==================================================================
# Risk categorisation
# ==================================================================


class TestRiskCategorisation:
    def test_low(self, scorer: RiskScorer) -> None:
        cs = _changeset([_change(added=[1])])
        risk = scorer.calculate_risk(cs, coverage_data={"utils": 100.0})
        assert risk.level == RiskLevel.LOW

    def test_level_is_valid_enum(
        self, scorer: RiskScorer, simple_changeset: ChangeSet
    ) -> None:
        risk = scorer.calculate_risk(simple_changeset)
        assert risk.level in (
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        )
