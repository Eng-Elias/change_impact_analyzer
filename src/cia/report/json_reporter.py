"""JSON report generation for CI/CD integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cia.analyzer.impact_analyzer import ImpactReport

# ---------------------------------------------------------------------------
# JSON schema (lightweight, for documentation / validation)
# ---------------------------------------------------------------------------

REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CIA Impact Report",
    "type": "object",
    "required": ["schema_version", "summary", "changes", "risk", "affected_modules"],
    "properties": {
        "schema_version": {"type": "string"},
        "summary": {
            "type": "object",
            "properties": {
                "total_files_changed": {"type": "integer"},
                "total_symbols_affected": {"type": "integer"},
                "total_modules_affected": {"type": "integer"},
            },
        },
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "change_type": {"type": "string"},
                    "added_lines": {"type": "integer"},
                    "deleted_lines": {"type": "integer"},
                    "directly_affected": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "transitively_affected": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "affected_modules": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "risk": {
            "type": ["object", "null"],
            "properties": {
                "overall_score": {"type": "number"},
                "level": {"type": "string"},
                "factor_scores": {"type": "object"},
                "explanations": {"type": "array", "items": {"type": "string"}},
                "suggestions": {"type": "array", "items": {"type": "string"}},
            },
        },
        "affected_modules": {"type": "array", "items": {"type": "string"}},
        "affected_tests": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
}

SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# JsonReporter
# ---------------------------------------------------------------------------


class JsonReporter:
    """Generates structured JSON reports suitable for CI/CD pipelines."""

    def generate(self, report: ImpactReport) -> str:
        """Generate a JSON string from the *ImpactReport*."""
        data = self.build_report_dict(report)
        return json.dumps(data, indent=2, default=str)

    def write(self, report: ImpactReport, output_path: Path) -> Path:
        """Write the JSON report to a file."""
        content = self.generate(report)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    @staticmethod
    def get_schema() -> dict[str, Any]:
        """Return the JSON-schema definition for the report."""
        return REPORT_SCHEMA

    @staticmethod
    def build_report_dict(report: ImpactReport) -> dict[str, Any]:
        """Build the structured report dictionary."""
        analysis = report.analysis

        changes = []
        for impact in analysis.impacts:
            changes.append(
                {
                    "file": str(impact.change.file_path),
                    "change_type": impact.change.change_type,
                    "added_lines": len(impact.change.added_lines),
                    "deleted_lines": len(impact.change.deleted_lines),
                    "directly_affected": impact.directly_affected,
                    "transitively_affected": impact.transitively_affected,
                    "affected_modules": impact.affected_modules,
                }
            )

        risk_dict: dict[str, Any] | None = None
        if report.risk is not None:
            risk_dict = {
                "overall_score": round(report.risk.overall_score, 1),
                "level": report.risk.level.value,
                "factor_scores": {
                    k: round(v, 1) for k, v in report.risk.factor_scores.items()
                },
                "explanations": report.risk.explanations,
                "suggestions": report.risk.suggestions,
            }

        return {
            "schema_version": SCHEMA_VERSION,
            "summary": {
                "total_files_changed": analysis.total_files_changed,
                "total_symbols_affected": analysis.total_symbols_affected,
                "total_modules_affected": analysis.total_modules_affected,
            },
            "changes": changes,
            "risk": risk_dict,
            "affected_modules": report.affected_modules,
            "affected_tests": [str(t) for t in report.affected_tests],
            "recommendations": report.recommendations,
        }
