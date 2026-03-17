"""Tests for HtmlReporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.analyzer.change_detector import Change
from cia.analyzer.impact_analyzer import (
    AnalysisReport,
    ImpactReport,
    ImpactResult,
)
from cia.report.html_reporter import HtmlReporter, _heatmap_color, _build_graph_data
from cia.risk.risk_factors import RiskLevel, RiskScore


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _change(path: str = "utils.py", added: int = 2, deleted: int = 1) -> Change:
    return Change(
        file_path=Path(path),
        change_type="modified",
        added_lines=list(range(1, added + 1)),
        deleted_lines=list(range(1, deleted + 1)),
    )


def _risk(score: float = 45.0, level: RiskLevel = RiskLevel.MEDIUM) -> RiskScore:
    return RiskScore(
        overall_score=score,
        level=level,
        factor_scores={"complexity": 30.0, "churn": 60.0},
        explanations=["Complexity: 30/100", "Churn: 60/100"],
        suggestions=["Add tests for utils"],
    )


def _report(
    *,
    risk: RiskScore | None = None,
    changes: list[Change] | None = None,
    affected_modules: list[str] | None = None,
    affected_tests: list[Path] | None = None,
    recommendations: list[str] | None = None,
) -> ImpactReport:
    changes = changes or [_change()]
    impacts = [
        ImpactResult(
            change=c,
            directly_affected=["core.run"],
            transitively_affected=["main.start"],
            affected_modules=["core"],
        )
        for c in changes
    ]
    analysis = AnalysisReport(
        impacts=impacts,
        total_files_changed=len(changes),
        total_symbols_affected=2,
        total_modules_affected=1,
    )
    return ImpactReport(
        analysis=analysis,
        risk=risk,
        affected_modules=affected_modules or ["core"],
        affected_tests=affected_tests or [],
        recommendations=recommendations or [],
    )


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def reporter() -> HtmlReporter:
    return HtmlReporter()


# ==================================================================
# HTML generation
# ==================================================================


class TestHtmlGeneration:
    def test_returns_string(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert isinstance(html, str)

    def test_contains_doctype(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "<!DOCTYPE html>" in html

    def test_contains_title(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "Change Impact Analysis Report" in html

    def test_executive_summary_section(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "Executive Summary" in html
        assert "Files changed:" in html

    def test_change_overview_table(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "utils.py" in html
        assert "modified" in html

    def test_dependency_impact_section(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(affected_modules=["core", "main"]))
        assert "Dependency Impact" in html
        assert "core" in html

    def test_collapsible_dependency_chains(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "collapsible" in html
        assert "toggle(this)" in html

    def test_no_changes(self, reporter: HtmlReporter) -> None:
        r = ImpactReport()
        html = reporter.generate(r)
        assert "No changes detected" in html


class TestHtmlRiskSection:
    def test_risk_badge(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(risk=_risk()))
        assert "badge-medium" in html
        assert "45.0" in html

    def test_risk_breakdown_table(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(risk=_risk()))
        assert "Risk Breakdown" in html
        assert "complexity" in html
        assert "churn" in html

    def test_heatmap_cells(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(risk=_risk()))
        assert "heatmap-cell" in html

    def test_risk_explanations(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(risk=_risk()))
        assert "Complexity: 30/100" in html

    def test_risk_suggestions(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(risk=_risk()))
        assert "Add tests for utils" in html

    def test_no_risk_section_when_none(self, reporter: HtmlReporter) -> None:
        r = ImpactReport()  # no risk at all
        html = reporter.generate(r)
        assert "Risk Breakdown" not in html


class TestHtmlTestRecommendations:
    def test_test_section(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(affected_tests=[Path("tests/test_utils.py")]))
        assert "Test Recommendations" in html
        assert "test_utils.py" in html

    def test_no_test_section_when_empty(self, reporter: HtmlReporter) -> None:
        r = ImpactReport()  # no affected tests
        html = reporter.generate(r)
        assert "Test Recommendations" not in html


class TestHtmlActionItems:
    def test_action_items(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report(recommendations=["Split the commit"]))
        assert "Action Items" in html
        assert "Split the commit" in html

    def test_no_action_items_when_empty(self, reporter: HtmlReporter) -> None:
        r = ImpactReport()  # no recommendations
        html = reporter.generate(r)
        assert "Action Items" not in html


class TestHtmlD3Graph:
    def test_d3_script_tag(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "d3.v7.min.js" in html

    def test_graph_json_embedded(self, reporter: HtmlReporter) -> None:
        html = reporter.generate(_report())
        assert "graphData" in html


class TestHtmlWrite:
    def test_write_creates_file(self, reporter: HtmlReporter, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        result = reporter.write(_report(), out)
        assert result == out
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content


# ==================================================================
# Helper functions
# ==================================================================


class TestHeatmapColor:
    def test_low(self) -> None:
        assert _heatmap_color(10) == "#22c55e"

    def test_medium(self) -> None:
        assert _heatmap_color(30) == "#eab308"

    def test_high(self) -> None:
        assert _heatmap_color(60) == "#f97316"

    def test_critical(self) -> None:
        assert _heatmap_color(80) == "#ef4444"

    def test_boundary_25(self) -> None:
        assert _heatmap_color(25) == "#22c55e"

    def test_boundary_26(self) -> None:
        assert _heatmap_color(26) == "#eab308"

    def test_boundary_51(self) -> None:
        assert _heatmap_color(51) == "#f97316"

    def test_boundary_76(self) -> None:
        assert _heatmap_color(76) == "#ef4444"


class TestBuildGraphData:
    def test_nodes_and_links(self) -> None:
        r = _report()
        data = _build_graph_data(r)
        assert "nodes" in data
        assert "links" in data
        assert len(data["nodes"]) > 0

    def test_changed_flag(self) -> None:
        r = _report()
        data = _build_graph_data(r)
        changed_nodes = [n for n in data["nodes"] if n["changed"]]
        assert len(changed_nodes) >= 1

    def test_empty_report(self) -> None:
        r = ImpactReport()
        data = _build_graph_data(r)
        assert data["nodes"] == []
        assert data["links"] == []
