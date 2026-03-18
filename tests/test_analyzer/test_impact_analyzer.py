"""Comprehensive tests for ImpactAnalyzer orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.analyzer.change_detector import Change, ChangeSet
from cia.analyzer.impact_analyzer import (
    AnalysisReport,
    ImpactAnalyzer,
    ImpactReport,
    ImpactResult,
)
from cia.graph.call_graph import CallGraph
from cia.graph.dependency_graph import DependencyGraph
from cia.parser.base import Symbol
from cia.risk.risk_factors import RiskLevel, RiskScore

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _change(
    path: str = "utils.py",
    symbols: list[Symbol] | None = None,
) -> Change:
    return Change(
        file_path=Path(path),
        change_type="modified",
        added_lines=[1, 2],
        deleted_lines=[3],
        affected_symbols=symbols or [],
    )


def _symbol(name: str = "helper", module: str = "utils") -> Symbol:
    return Symbol(
        name=name,
        qualified_name=f"{module}.{name}",
        symbol_type="function",
        file_path=Path(f"{module}.py"),
        line_start=1,
        line_end=10,
    )


def _changeset(changes: list[Change] | None = None) -> ChangeSet:
    changes = changes or []
    return ChangeSet(
        changes=changes,
        added=[],
        modified=[c.file_path for c in changes],
        deleted=[],
    )


def _risk_score(
    score: float = 30.0,
    level: RiskLevel = RiskLevel.MEDIUM,
    suggestions: list[str] | None = None,
) -> RiskScore:
    return RiskScore(
        overall_score=score,
        level=level,
        factor_scores={"complexity": 20.0},
        explanations=["Complexity: 20/100"],
        suggestions=suggestions or [],
    )


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def dep_graph() -> DependencyGraph:
    g = DependencyGraph()
    g.add_module("utils")
    g.add_module("core")
    g.add_module("main")
    g.add_dependency("core", "utils")
    g.add_dependency("main", "core")
    return g


@pytest.fixture
def call_graph() -> CallGraph:
    cg = CallGraph()
    cg.add_function("utils", "helper")
    cg.add_function("core", "run")
    cg.add_call("core.run", "utils.helper")
    return cg


@pytest.fixture
def analyzer(dep_graph: DependencyGraph, call_graph: CallGraph) -> ImpactAnalyzer:
    return ImpactAnalyzer(dep_graph, call_graph)


@pytest.fixture
def analyzer_no_call(dep_graph: DependencyGraph) -> ImpactAnalyzer:
    return ImpactAnalyzer(dep_graph)


# ==================================================================
# ImpactResult / AnalysisReport dataclasses
# ==================================================================


class TestDataClasses:
    def test_impact_result_defaults(self) -> None:
        c = _change()
        r = ImpactResult(change=c)
        assert r.directly_affected == []
        assert r.transitively_affected == []
        assert r.affected_modules == []

    def test_analysis_report_defaults(self) -> None:
        ar = AnalysisReport()
        assert ar.impacts == []
        assert ar.total_files_changed == 0

    def test_impact_report_defaults(self) -> None:
        ir = ImpactReport()
        assert ir.risk is None
        assert ir.affected_tests == []
        assert ir.recommendations == []

    def test_impact_report_to_dict(self) -> None:
        ir = ImpactReport(
            affected_modules=["utils"],
            affected_tests=[Path("tests/test_utils.py")],
            recommendations=["Review code"],
        )
        d = ir.to_dict()
        assert d["affected_modules"] == ["utils"]
        assert "test_utils.py" in d["affected_tests"][0]
        assert "Review code" in d["recommendations"]

    def test_impact_report_to_dict_with_risk(self) -> None:
        ir = ImpactReport(risk=_risk_score())
        d = ir.to_dict()
        assert "risk_score" in d
        assert "risk_level" in d
        assert d["risk_level"] == "medium"


# ==================================================================
# Core analyze()
# ==================================================================


class TestAnalyze:
    def test_empty_changes(self, analyzer: ImpactAnalyzer) -> None:
        report = analyzer.analyze([])
        assert report.total_files_changed == 0
        assert report.impacts == []

    def test_single_change_no_symbols(self, analyzer: ImpactAnalyzer) -> None:
        report = analyzer.analyze([_change()])
        assert report.total_files_changed == 1
        assert len(report.impacts) == 1

    def test_change_with_symbols(self, analyzer: ImpactAnalyzer) -> None:
        sym = _symbol("helper", "utils")
        change = _change("utils.py", symbols=[sym])
        report = analyzer.analyze([change])
        assert report.total_symbols_affected > 0

    def test_affected_modules(self, analyzer: ImpactAnalyzer) -> None:
        change = _change("utils.py")
        report = analyzer.analyze([change])
        # core depends on utils → should be in affected_modules
        assert "core" in report.impacts[0].affected_modules

    def test_call_graph_callers(self, analyzer: ImpactAnalyzer) -> None:
        sym = _symbol("helper", "utils")
        change = _change("utils.py", symbols=[sym])
        report = analyzer.analyze([change])
        impact = report.impacts[0]
        assert "core.run" in impact.directly_affected

    def test_no_call_graph(self, analyzer_no_call: ImpactAnalyzer) -> None:
        change = _change("utils.py")
        report = analyzer_no_call.analyze([change])
        assert report.total_files_changed == 1


# ==================================================================
# analyze_change_set (orchestrator)
# ==================================================================


class TestAnalyzeChangeSet:
    def test_basic(self, analyzer: ImpactAnalyzer) -> None:
        cs = _changeset([_change()])
        ir = analyzer.analyze_change_set(cs)
        assert isinstance(ir, ImpactReport)
        assert ir.analysis.total_files_changed == 1

    def test_with_risk(self, analyzer: ImpactAnalyzer) -> None:
        cs = _changeset([_change()])
        risk = _risk_score()
        ir = analyzer.analyze_change_set(cs, risk_score=risk)
        assert ir.risk is not None
        assert ir.risk.overall_score == 30.0

    def test_with_affected_tests(self, analyzer: ImpactAnalyzer) -> None:
        cs = _changeset([_change()])
        tests = [Path("tests/test_utils.py")]
        ir = analyzer.analyze_change_set(cs, affected_tests=tests)
        assert ir.affected_tests == tests

    def test_affected_modules_populated(self, analyzer: ImpactAnalyzer) -> None:
        cs = _changeset([_change("utils.py")])
        ir = analyzer.analyze_change_set(cs)
        assert "utils" in ir.affected_modules


# ==================================================================
# combine_graph_analysis
# ==================================================================


class TestCombineGraphAnalysis:
    def test_basic(self, dep_graph: DependencyGraph) -> None:
        changes = [_change("utils.py")]
        result = ImpactAnalyzer.combine_graph_analysis(dep_graph, changes)
        assert "utils" in result
        assert "core" in result

    def test_sorted(self, dep_graph: DependencyGraph) -> None:
        changes = [_change("utils.py")]
        result = ImpactAnalyzer.combine_graph_analysis(dep_graph, changes)
        assert result == sorted(result)

    def test_empty_changes(self, dep_graph: DependencyGraph) -> None:
        result = ImpactAnalyzer.combine_graph_analysis(dep_graph, [])
        assert result == []

    def test_unknown_module(self, dep_graph: DependencyGraph) -> None:
        changes = [_change("unknown.py")]
        result = ImpactAnalyzer.combine_graph_analysis(dep_graph, changes)
        assert "unknown" in result


# ==================================================================
# combine_risk_analysis
# ==================================================================


class TestCombineRiskAnalysis:
    def test_empty(self) -> None:
        combined = ImpactAnalyzer.combine_risk_analysis([])
        assert combined.overall_score == 0.0

    def test_single(self) -> None:
        rs = _risk_score(40.0, RiskLevel.MEDIUM)
        combined = ImpactAnalyzer.combine_risk_analysis([rs])
        assert combined.overall_score == 40.0
        assert combined.level == RiskLevel.MEDIUM

    def test_takes_maximum(self) -> None:
        rs1 = _risk_score(20.0, RiskLevel.LOW)
        rs2 = _risk_score(60.0, RiskLevel.HIGH)
        combined = ImpactAnalyzer.combine_risk_analysis([rs1, rs2])
        assert combined.overall_score == 60.0
        assert combined.level == RiskLevel.HIGH

    def test_merges_factors(self) -> None:
        rs1 = RiskScore(overall_score=10, level=RiskLevel.LOW, factor_scores={"a": 10})
        rs2 = RiskScore(overall_score=20, level=RiskLevel.LOW, factor_scores={"a": 30, "b": 20})
        combined = ImpactAnalyzer.combine_risk_analysis([rs1, rs2])
        assert combined.factor_scores["a"] == 30
        assert combined.factor_scores["b"] == 20

    def test_deduplicates_explanations(self) -> None:
        rs1 = RiskScore(overall_score=10, level=RiskLevel.LOW, explanations=["A"])
        rs2 = RiskScore(overall_score=10, level=RiskLevel.LOW, explanations=["A", "B"])
        combined = ImpactAnalyzer.combine_risk_analysis([rs1, rs2])
        assert combined.explanations == ["A", "B"]


# ==================================================================
# generate_recommendations
# ==================================================================


class TestGenerateRecommendations:
    def test_no_recommendations_for_small(self) -> None:
        ar = AnalysisReport(total_modules_affected=2)
        recs = ImpactAnalyzer.generate_recommendations(ar)
        assert recs == []

    def test_large_blast_radius(self) -> None:
        ar = AnalysisReport(total_modules_affected=8)
        recs = ImpactAnalyzer.generate_recommendations(ar)
        assert any("blast radius" in r.lower() for r in recs)

    def test_high_risk(self) -> None:
        ar = AnalysisReport()
        risk = _risk_score(70.0, RiskLevel.HIGH)
        recs = ImpactAnalyzer.generate_recommendations(ar, risk_score=risk)
        assert any("review" in r.lower() for r in recs)

    def test_critical_risk(self) -> None:
        ar = AnalysisReport()
        risk = _risk_score(80.0, RiskLevel.CRITICAL)
        recs = ImpactAnalyzer.generate_recommendations(ar, risk_score=risk)
        assert any("review" in r.lower() for r in recs)

    def test_low_risk_no_review_rec(self) -> None:
        ar = AnalysisReport()
        risk = _risk_score(10.0, RiskLevel.LOW)
        recs = ImpactAnalyzer.generate_recommendations(ar, risk_score=risk)
        assert not any("review is strongly" in r.lower() for r in recs)

    def test_many_affected_modules(self) -> None:
        ar = AnalysisReport()
        modules = [f"mod{i}" for i in range(15)]
        recs = ImpactAnalyzer.generate_recommendations(ar, affected_modules=modules)
        assert any("integration" in r.lower() for r in recs)

    def test_risk_suggestions_included(self) -> None:
        ar = AnalysisReport()
        risk = _risk_score(70.0, RiskLevel.HIGH, suggestions=["Add more tests"])
        recs = ImpactAnalyzer.generate_recommendations(ar, risk_score=risk)
        assert "Add more tests" in recs
