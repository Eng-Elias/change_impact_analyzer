"""JSON report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cia.analyzer.impact_analyzer import AnalysisReport
from cia.risk.risk_scorer import RiskAssessment


class JsonReporter:
    """Generates impact analysis reports in JSON format."""

    def generate(
        self,
        report: AnalysisReport,
        risk_assessments: list[RiskAssessment] | None = None,
    ) -> str:
        """Generate a JSON string from the analysis report."""
        data = self._build_report_dict(report, risk_assessments)
        return json.dumps(data, indent=2, default=str)

    def write(
        self,
        report: AnalysisReport,
        output_path: Path,
        risk_assessments: list[RiskAssessment] | None = None,
    ) -> Path:
        """Write the JSON report to a file."""
        content = self.generate(report, risk_assessments)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def _build_report_dict(
        self,
        report: AnalysisReport,
        risk_assessments: list[RiskAssessment] | None,
    ) -> dict[str, Any]:
        """Build the report dictionary."""
        impacts = []
        for i, impact in enumerate(report.impacts):
            entry: dict[str, Any] = {
                "file": str(impact.change.file_path),
                "change_type": impact.change.change_type,
                "directly_affected": impact.directly_affected,
                "transitively_affected": impact.transitively_affected,
                "affected_modules": impact.affected_modules,
            }
            if risk_assessments and i < len(risk_assessments):
                ra = risk_assessments[i]
                entry["risk"] = {
                    "score": round(ra.score, 3),
                    "level": ra.level.value,
                }
            impacts.append(entry)

        return {
            "summary": {
                "total_files_changed": report.total_files_changed,
                "total_symbols_affected": report.total_symbols_affected,
                "total_modules_affected": report.total_modules_affected,
            },
            "impacts": impacts,
        }
