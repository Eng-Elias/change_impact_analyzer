"""Tests for MarkdownReporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from cia.analyzer.change_detector import Change
from cia.analyzer.impact_analyzer import (
    AnalysisReport,
    ImpactReport,
    ImpactResult,
)
from cia.report.markdown_reporter import MarkdownReporter
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
def reporter() -> MarkdownReporter:
    return MarkdownReporter()


# ==================================================================
# Markdown generation
# ==================================================================


class TestMarkdownGeneration:
    def test_returns_string(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report())
        assert isinstance(md, str)

    def test_title(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report())
        assert "# Change Impact Analysis Report" in md

    def test_executive_summary(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report())
        assert "## Executive Summary" in md
        assert "Files changed:" in md

    def test_change_overview_table(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report())
        assert "## Change Overview" in md
        assert "| File |" in md
        assert "utils.py" in md

    def test_multiple_changes(self, reporter: MarkdownReporter) -> None:
        changes = [_change("a.py"), _change("b.py")]
        md = reporter.generate(_report(changes=changes))
        assert "a.py" in md
        assert "b.py" in md

    def test_empty_report(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(ImpactReport())
        assert "# Change Impact Analysis Report" in md
        assert "Change Overview" not in md


class TestMarkdownDependencyImpact:
    def test_affected_modules(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(affected_modules=["core", "main"]))
        assert "## Dependency Impact" in md
        assert "`core`" in md
        assert "`main`" in md

    def test_directly_affected(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report())
        assert "Directly affected" in md
        assert "`core.run`" in md

    def test_transitively_affected(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report())
        assert "Transitively affected" in md
        assert "`main.start`" in md

    def test_no_dependency_section_when_empty(self, reporter: MarkdownReporter) -> None:
        r = ImpactReport()  # no affected modules, no impacts
        md = reporter.generate(r)
        assert "## Dependency Impact" not in md


class TestMarkdownRisk:
    def test_risk_badge(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(risk=_risk()))
        assert "MEDIUM" in md
        assert "45.0/100" in md

    def test_risk_breakdown_table(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(risk=_risk()))
        assert "## Risk Breakdown" in md
        assert "| complexity |" in md
        assert "| churn |" in md

    def test_risk_explanations(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(risk=_risk()))
        assert "Complexity: 30/100" in md

    def test_no_risk_when_none(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(risk=None))
        assert "Risk Breakdown" not in md

    def test_risk_emoji(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(risk=_risk()))
        # Should contain an emoji character (circle)
        assert "\U0001f7e1" in md  # yellow circle for medium

    def test_risk_suggestions(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(risk=_risk()))
        assert "Add tests for utils" in md


class TestMarkdownTestRecommendations:
    def test_test_section(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(affected_tests=[Path("tests/test_utils.py")]))
        assert "## Test Recommendations" in md
        assert "test_utils.py" in md

    def test_test_count(self, reporter: MarkdownReporter) -> None:
        tests = [Path("tests/test_a.py"), Path("tests/test_b.py")]
        md = reporter.generate(_report(affected_tests=tests))
        assert "Tests to run:** 2" in md

    def test_no_test_section_when_empty(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(affected_tests=[]))
        assert "Test Recommendations" not in md


class TestMarkdownActionItems:
    def test_action_items(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(recommendations=["Split the commit"]))
        assert "## Action Items" in md
        assert "Split the commit" in md

    def test_numbered_list(self, reporter: MarkdownReporter) -> None:
        recs = ["First action", "Second action"]
        md = reporter.generate(_report(recommendations=recs))
        assert "1. First action" in md
        assert "2. Second action" in md

    def test_no_action_items_when_empty(self, reporter: MarkdownReporter) -> None:
        md = reporter.generate(_report(recommendations=[]))
        assert "Action Items" not in md


class TestMarkdownWrite:
    def test_write_creates_file(
        self, reporter: MarkdownReporter, tmp_path: Path
    ) -> None:
        out = tmp_path / "report.md"
        result = reporter.write(_report(), out)
        assert result == out
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "# Change Impact Analysis Report" in content
