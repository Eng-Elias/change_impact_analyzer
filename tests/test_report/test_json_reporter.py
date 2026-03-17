"""Tests for JsonReporter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cia.analyzer.change_detector import Change
from cia.analyzer.impact_analyzer import (
    AnalysisReport,
    ImpactReport,
    ImpactResult,
)
from cia.report.json_reporter import JsonReporter, REPORT_SCHEMA, SCHEMA_VERSION
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
        explanations=["Complexity: 30/100"],
        suggestions=["Add tests"],
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
            transitively_affected=[],
            affected_modules=["core"],
        )
        for c in changes
    ]
    analysis = AnalysisReport(
        impacts=impacts,
        total_files_changed=len(changes),
        total_symbols_affected=1,
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
def reporter() -> JsonReporter:
    return JsonReporter()


# ==================================================================
# JSON generation
# ==================================================================


class TestJsonGeneration:
    def test_returns_valid_json(self, reporter: JsonReporter) -> None:
        output = reporter.generate(_report())
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_schema_version(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report()))
        assert data["schema_version"] == SCHEMA_VERSION

    def test_summary_section(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report()))
        assert "summary" in data
        assert data["summary"]["total_files_changed"] == 1

    def test_changes_section(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report()))
        assert "changes" in data
        assert len(data["changes"]) == 1
        c = data["changes"][0]
        assert c["file"] == "utils.py"
        assert c["change_type"] == "modified"
        assert c["added_lines"] == 2
        assert c["deleted_lines"] == 1

    def test_directly_affected(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report()))
        assert "core.run" in data["changes"][0]["directly_affected"]

    def test_affected_modules(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(affected_modules=["core", "main"])))
        assert data["affected_modules"] == ["core", "main"]

    def test_affected_tests(self, reporter: JsonReporter) -> None:
        r = _report(affected_tests=[Path("tests/test_utils.py")])
        data = json.loads(reporter.generate(r))
        assert len(data["affected_tests"]) == 1
        assert "test_utils.py" in data["affected_tests"][0]

    def test_recommendations(self, reporter: JsonReporter) -> None:
        r = _report(recommendations=["Review carefully"])
        data = json.loads(reporter.generate(r))
        assert "Review carefully" in data["recommendations"]

    def test_multiple_changes(self, reporter: JsonReporter) -> None:
        changes = [_change("a.py"), _change("b.py")]
        data = json.loads(reporter.generate(_report(changes=changes)))
        assert len(data["changes"]) == 2

    def test_empty_report(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(ImpactReport()))
        assert data["changes"] == []
        assert data["risk"] is None


class TestJsonRisk:
    def test_risk_present(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(risk=_risk())))
        assert data["risk"] is not None
        assert data["risk"]["overall_score"] == 45.0
        assert data["risk"]["level"] == "medium"

    def test_risk_factor_scores(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(risk=_risk())))
        assert "complexity" in data["risk"]["factor_scores"]
        assert "churn" in data["risk"]["factor_scores"]

    def test_risk_explanations(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(risk=_risk())))
        assert "Complexity: 30/100" in data["risk"]["explanations"]

    def test_risk_suggestions(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(risk=_risk())))
        assert "Add tests" in data["risk"]["suggestions"]

    def test_risk_null_when_absent(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(risk=None)))
        assert data["risk"] is None


# ==================================================================
# JSON schema compliance
# ==================================================================


class TestJsonSchema:
    def test_schema_has_required_fields(self) -> None:
        assert "required" in REPORT_SCHEMA
        required = REPORT_SCHEMA["required"]
        assert "schema_version" in required
        assert "summary" in required
        assert "changes" in required
        assert "risk" in required

    def test_schema_properties(self) -> None:
        props = REPORT_SCHEMA["properties"]
        assert "schema_version" in props
        assert "summary" in props
        assert "changes" in props
        assert "risk" in props
        assert "affected_modules" in props
        assert "affected_tests" in props
        assert "recommendations" in props

    def test_get_schema(self, reporter: JsonReporter) -> None:
        schema = reporter.get_schema()
        assert schema is REPORT_SCHEMA

    def test_output_has_all_required_keys(self, reporter: JsonReporter) -> None:
        data = json.loads(reporter.generate(_report(risk=_risk())))
        for key in REPORT_SCHEMA["required"]:
            assert key in data, f"Missing required key: {key}"


# ==================================================================
# Write to file
# ==================================================================


class TestJsonWrite:
    def test_write_creates_file(self, reporter: JsonReporter, tmp_path: Path) -> None:
        out = tmp_path / "report.json"
        result = reporter.write(_report(), out)
        assert result == out
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "schema_version" in data


# ==================================================================
# build_report_dict
# ==================================================================


class TestBuildReportDict:
    def test_returns_dict(self, reporter: JsonReporter) -> None:
        d = reporter.build_report_dict(_report())
        assert isinstance(d, dict)

    def test_risk_scores_rounded(self, reporter: JsonReporter) -> None:
        r = _risk(45.678)
        d = reporter.build_report_dict(_report(risk=r))
        assert d["risk"]["overall_score"] == 45.7
